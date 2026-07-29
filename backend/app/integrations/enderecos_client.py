"""I/O das consultas de CEP/CNPJ em APIs publicas.

Sincrono e com erro que sobe, de proposito: o usuario esta esperando o resultado
na tela. Difere do taskhs_client, que e' best-effort e engole tudo.
"""
import logging

import httpx

from app.core import enderecos

logger = logging.getLogger(__name__)

TIMEOUT = 5
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
    """Sem fallback: a ReceitaWS limita a 3 req/min e daria mais erro do que ajuda."""
    digitos = enderecos.validar_cnpj(cnpj)
    dados = _get_json(URL_BRASILAPI_CNPJ.format(cnpj=digitos))
    if dados is None:
        raise enderecos.NaoEncontrado("CNPJ nao encontrado")
    return enderecos.mapear_brasilapi_cnpj(dados)
