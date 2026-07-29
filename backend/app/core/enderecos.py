"""Consulta de CEP/CNPJ em APIs publicas: validacao de formato, normalizacao de
texto e mapeamento do JSON de cada provedor para o formato unico do GestorHS.

Puro, sem I/O — as chamadas HTTP vivem em app/integrations/enderecos_client.py.
"""
import re

# Conectivos que ficam minusculos no meio do nome ("Cais do Apolo").
_CONECTIVOS = {"de", "da", "do", "das", "dos", "e"}

_VOGAIS = set("AEIOUaeiou")

# Sufixos societarios curtos e comuns em razao_social de CNPJ que TEM vogal
# mas ainda sao sigla ("SA", "ME", "EPP") — a heuristica "sem vogal" sozinha
# nao os distingue de palavras comuns, entao precisam de lista propria.
_SIGLAS_SOCIETARIAS = {"SA", "ME", "EPP"}


def _e_sigla(token: str) -> bool:
    """Sigla = token curto todo maiusculo que e (a) um sufixo societario
    conhecido ("SA", "ME", "EPP"), (b) sem vogal ("BR", "KM", "CBF") ou
    (c) com caracter nao alfabetico ("S/A") — nao e uma palavra comum como
    "RUA" (curta, so letras, com vogal, fora da lista societaria).
    """
    if not (len(token) <= 3 and token.isupper()):
        return False
    if token in _SIGLAS_SOCIETARIAS:
        return True
    return not token.isalpha() or not any(c in _VOGAIS for c in token)


class DocumentoInvalido(ValueError):
    """CEP/CNPJ fora do formato esperado. Checado ANTES de sair para a rede."""


class NaoEncontrado(Exception):
    """O provedor respondeu, mas nao conhece esse CEP/CNPJ."""


class ProvedorIndisponivel(Exception):
    """Falha de rede ou erro do provedor."""


def so_digitos(v) -> str:
    return re.sub(r"\D", "", str(v or ""))


def validar_cep(cep: str) -> str:
    d = so_digitos(cep)
    if len(d) != 8:
        raise DocumentoInvalido("CEP deve ter 8 digitos")
    return d


def validar_cnpj(cnpj: str) -> str:
    d = so_digitos(cnpj)
    if len(d) != 14:
        raise DocumentoInvalido("CNPJ deve ter 14 digitos")
    return d


def capitalizar(texto) -> str:
    """Converte o CAIXA ALTA da Receita para forma capitalizada.

    Preserva o que nao deve ser mexido: tokens com digito ("101", "196,5"),
    siglas de ate 3 caracteres em maiuscula sem vogal ou com caracter nao
    alfabetico ("BR", "KM", "CBF", "S/A") e sufixos societarios comuns em
    razao_social de CNPJ ("SA", "ME", "EPP") — o que evita capturar palavras
    curtas comuns como "RUA". Conectivos ficam minusculos, exceto na
    primeira palavra.

    NAO restaura acentuacao — a fonte ja veio sem ela ("JOAO" -> "Joao").
    """
    if not texto:
        return ""
    saida = []
    for i, token in enumerate(str(texto).split()):
        if any(c.isdigit() for c in token):
            saida.append(token)
        elif i > 0 and token.lower() in _CONECTIVOS:
            saida.append(token.lower())
        elif _e_sigla(token):
            saida.append(token)
        else:
            saida.append(token.capitalize())
    return " ".join(saida)


def mapear_brasilapi_cep(dados: dict) -> dict:
    return {
        "cep": so_digitos(dados.get("cep")),
        "endereco": capitalizar(dados.get("street")),
        "municipio": capitalizar(dados.get("city")),
        "estado": str(dados.get("state") or "").upper(),
    }


def mapear_viacep(dados: dict) -> dict:
    # A ViaCEP sinaliza CEP inexistente com HTTP 200 + {"erro": true}.
    if dados.get("erro"):
        raise NaoEncontrado("CEP nao encontrado")
    return {
        "cep": so_digitos(dados.get("cep")),
        "endereco": capitalizar(dados.get("logradouro")),
        "municipio": capitalizar(dados.get("localidade")),
        "estado": str(dados.get("uf") or "").upper(),
    }


def mapear_brasilapi_cnpj(dados: dict) -> dict:
    endereco = capitalizar(dados.get("logradouro"))
    numero = str(dados.get("numero") or "").strip()
    complemento = capitalizar(dados.get("complemento"))
    if numero:
        endereco = f"{endereco}, {numero}" if endereco else numero
    if complemento:
        endereco = f"{endereco} {complemento}".strip()
    return {
        "documento": so_digitos(dados.get("cnpj")),
        "nome": capitalizar(dados.get("razao_social")),
        "endereco": endereco,
        "municipio": capitalizar(dados.get("municipio")),
        "estado": str(dados.get("uf") or "").upper(),
        "cep": so_digitos(dados.get("cep")),
        "situacao": str(dados.get("descricao_situacao_cadastral") or "").upper(),
    }
