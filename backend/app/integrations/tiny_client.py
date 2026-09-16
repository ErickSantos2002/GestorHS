"""Cliente HTTP do Tiny ERP (API v2). Best-effort, gating por TINY_TOKEN.

Nenhuma funcao levanta: todas devolvem `Resultado` (app/core/tiny.py) e
registram em `log_integracao`. O Tiny responde HTTP 200 mesmo em erro — quem
manda e' o corpo.
"""
import json
import logging
from typing import Optional

import httpx

from app.core import tiny
from app.core.config import settings
from app.integrations.log_integracao import registrar_log_integracao

logger = logging.getLogger(__name__)

TIMEOUT = 20


def integracao_ativa() -> bool:
    return bool(settings.TINY_TOKEN)


def _chamar(endpoint: str, dados: dict, *, referencia: Optional[str] = None) -> tiny.Resultado:
    if not integracao_ativa():
        registrar_log_integracao(integracao="tiny", status="pulado", motivo="desligado",
                                 payload={"endpoint": endpoint, "external_id": referencia})
        return tiny.Resultado(ok=False, mensagem="integracao com o Tiny desligada")

    url = f"{settings.TINY_BASE_URL.rstrip('/')}/{endpoint}"
    payload = {"endpoint": endpoint, "external_id": referencia}
    try:
        resp = httpx.post(url, data={"token": settings.TINY_TOKEN, "formato": "json", **dados},
                          timeout=TIMEOUT)
    except Exception as e:  # noqa: BLE001 - best-effort: rede nunca derruba o chamador
        registrar_log_integracao(integracao="tiny", status="erro", payload=payload, resposta=str(e))
        logger.warning("falha de rede no Tiny (%s): %s", endpoint, e)
        # Falha de rede passa sozinha: tratada como "tentar de novo" (codigo de limite).
        return tiny.Resultado(ok=False, codigo_erro=tiny.LIMITE[0], mensagem=str(e))

    try:
        corpo = resp.json()
    except Exception:  # noqa: BLE001 - corpo fora do formato tambem e' falha, nao excecao
        registrar_log_integracao(integracao="tiny", status="erro", payload=payload,
                                 http_status=resp.status_code, resposta=resp.text)
        return tiny.Resultado(ok=False, mensagem="resposta do Tiny nao e' JSON")

    resultado = tiny.ler_resposta(corpo)
    registrar_log_integracao(
        integracao="tiny",
        status="sucesso" if resultado.ok else "erro",
        payload=payload,
        http_status=resp.status_code,
        resposta=resp.text,
        motivo=None if resultado.ok else f"codigo_erro={resultado.codigo_erro}",
    )
    return resultado


def pesquisar_contato(documento: str) -> tiny.Resultado:
    """Acha o contato pelo CNPJ/CPF. `nao_encontrado` = erro 20, que NAO e' falha."""
    return _chamar("contatos.pesquisa.php",
                   {"pesquisa": "", "cpf_cnpj": documento}, referencia=documento)


def obter_contato(tiny_id: int) -> tiny.Resultado:
    return _chamar("contato.obter.php", {"id": tiny_id}, referencia=str(tiny_id))


def obter_contato_bruto(tiny_id: int) -> Optional[dict]:
    """O contato como o Tiny guarda — base da alteracao, que apaga o que faltar."""
    payload = {"endpoint": "contato.obter.php", "external_id": str(tiny_id)}
    if not integracao_ativa():
        registrar_log_integracao(integracao="tiny", status="pulado", motivo="desligado", payload=payload)
        return None
    url = f"{settings.TINY_BASE_URL.rstrip('/')}/contato.obter.php"
    try:
        resp = httpx.post(url, data={"token": settings.TINY_TOKEN, "formato": "json", "id": tiny_id},
                          timeout=TIMEOUT)
        corpo = resp.json()
    except Exception as e:  # noqa: BLE001
        registrar_log_integracao(integracao="tiny", status="erro", payload=payload, resposta=str(e))
        return None
    contato = (corpo.get("retorno") or {}).get("contato")
    encontrado = isinstance(contato, dict)
    registrar_log_integracao(
        integracao="tiny",
        status="sucesso" if encontrado else "erro",
        payload=payload,
        http_status=resp.status_code,
        resposta=resp.text,
    )
    return contato if encontrado else None


def incluir_contato(contato: dict) -> tiny.Resultado:
    return _chamar("contato.incluir.php", {"contato": _envelope(contato)},
                   referencia=contato.get("cpf_cnpj"))


def alterar_contato(contato: dict) -> tiny.Resultado:
    return _chamar("contato.alterar.php", {"contato": _envelope(contato)},
                   referencia=str(contato.get("id")))


def _envelope(contato: dict) -> str:
    """A v2 recebe o contato como JSON dentro de um campo de formulario."""
    return json.dumps({"contatos": [{"contato": contato}]}, ensure_ascii=False)
