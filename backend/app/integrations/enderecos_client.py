"""I/O das consultas de CEP/CNPJ em APIs publicas.

Sincrono e com erro que sobe, de proposito: o usuario esta esperando o resultado
na tela. Difere do taskhs_client, que e' best-effort e engole tudo.
"""
import logging
import time

import httpx

from app.core import enderecos

logger = logging.getLogger(__name__)

# Timeout por FASE, nao total: com um numero solto o httpx aplica 5s em cada uma
# (conexao, escrita, leitura), e um provedor travado podia segurar a requisicao
# por ~15s — tempo de sobra para o proxy na frente da API desistir antes e
# devolver um 502 dele, sem os cabecalhos CORS que a aplicacao poe. Aqui o pior
# caso fica em ~9s, dentro da folga do proxy.
TIMEOUT = httpx.Timeout(5.0, connect=3.0, write=1.0)

# Uma unica nova tentativa quando a cota estoura. A pausa e' curta de proposito:
# o usuario esta parado na tela olhando a lupa girar.
PAUSA_NOVA_TENTATIVA = 1.5
URL_BRASILAPI_CEP = "https://brasilapi.com.br/api/cep/v2/{cep}"
URL_VIACEP = "https://viacep.com.br/ws/{cep}/json/"
URL_BRASILAPI_CNPJ = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"


def _get_json(url: str):
    """GET que devolve o JSON, None em 404 e levanta ProvedorIndisponivel no resto.

    So captura httpx.HTTPError (a arvore de erro de transporte/HTTP do httpx:
    ConnectError, TimeoutException, etc.) — um bug de programacao (TypeError,
    AttributeError...) deve estourar, nao virar um falso "provedor fora do ar".
    """
    try:
        resp = httpx.get(url, timeout=TIMEOUT)
    except httpx.HTTPError as e:
        raise enderecos.ProvedorIndisponivel(str(e)) from e
    if resp.status_code == 404:
        return None
    if resp.status_code == 429:
        raise enderecos.LimiteExcedido("cota do provedor excedida")
    if resp.status_code >= 400:
        raise enderecos.ProvedorIndisponivel(f"HTTP {resp.status_code}")
    try:
        return resp.json()
    except ValueError as e:
        raise enderecos.ProvedorIndisponivel("resposta nao e JSON") from e


def buscar_cep(cep: str) -> dict:
    """BrasilAPI primeiro, ViaCEP como fallback — tanto para falha quanto para 404,
    porque a BrasilAPI agrega provedores que caem individualmente."""
    digitos = enderecos.validar_cep(cep)
    try:
        dados = _get_json(URL_BRASILAPI_CEP.format(cep=digitos))
        if dados is not None:
            return enderecos.mapear_brasilapi_cep(dados)
    except enderecos.ProvedorIndisponivel as e:
        logger.warning("BrasilAPI CEP indisponivel (%s); tentando ViaCEP", e)
    dados = _get_json(URL_VIACEP.format(cep=digitos))
    if dados is None:
        raise enderecos.NaoEncontrado("CEP nao encontrado")
    return enderecos.mapear_viacep(dados)


def buscar_cnpj(cnpj: str) -> dict:
    """Sem provedor alternativo: a ReceitaWS limita a 3 req/min e daria mais erro
    do que ajuda. O que existe e' uma segunda tentativa no MESMO provedor quando
    a cota estoura — cota passa sozinha em segundos, provedor fora do ar nao,
    entao so o 429 e' repetido.
    """
    digitos = enderecos.validar_cnpj(cnpj)
    url = URL_BRASILAPI_CNPJ.format(cnpj=digitos)
    try:
        dados = _get_json(url)
    except enderecos.LimiteExcedido:
        logger.warning("BrasilAPI CNPJ recusou por cota; tentando de novo em %ss", PAUSA_NOVA_TENTATIVA)
        time.sleep(PAUSA_NOVA_TENTATIVA)
        dados = _get_json(url)
    if dados is None:
        raise enderecos.NaoEncontrado("CNPJ nao encontrado")
    return enderecos.mapear_brasilapi_cnpj(dados)
