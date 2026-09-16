"""Cliente HTTP do Tiny ERP (API v2). Best-effort, gating por TINY_TOKEN.

Nenhuma funcao levanta: todas devolvem `Resultado` (app/core/tiny.py) e
registram em `log_integracao`. O Tiny responde HTTP 200 mesmo em erro — quem
manda e' o corpo.
"""
import json
import logging
from datetime import datetime, timezone
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
        # Falha de rede passa sozinha, mas NAO e' bloqueio do Tiny: marcar o
        # codigo 6 fazia o script anunciar excesso de chamadas quando caiu a rede.
        return tiny.Resultado(ok=False, tentar_de_novo=True, mensagem=str(e))

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


def _marcar(db, empresa, *, status: str, erro: Optional[str] = None,
            tiny_id: Optional[int] = None) -> None:
    if tiny_id is not None:
        empresa.tiny_id = tiny_id
    empresa.tiny_status = status
    empresa.tiny_erro = (erro or "")[:255] or None
    empresa.tiny_em = datetime.now(timezone.utc)
    db.commit()


def sincronizar_empresa(empresa_id: int, *, db=None) -> None:
    """Alvo do BackgroundTask: espelha UMA Empresa no Tiny. Nunca propaga.

    Sem `tiny_id`: pesquisa pelo documento e ADOTA o contato que existir (as
    filiais ja estao cadastradas la); so cria o que faltar.
    Com `tiny_id`: le o contato e reenvia INTEIRO — `contato.alterar.php` apaga
    o que nao for enviado.
    """
    from app.models import Empresa
    from app.models.database import SessionLocal

    if not integracao_ativa():
        return

    propria = db is None
    db = db or SessionLocal()
    try:
        empresa = db.get(Empresa, empresa_id)
        if empresa is None:
            return
        documento = empresa.cgc or empresa.cpf or ""

        if empresa.tiny_id:
            atual = obter_contato_bruto(empresa.tiny_id)
            if atual is not None:
                resultado = alterar_contato(tiny.contato_para_alterar(empresa, atual))
                _aplicar(db, empresa, resultado, manter_id=True)
                return
            if not documento:
                # `obter` devolve None por quatro motivos (apagado, rede, corpo
                # invalido, limite). Sem documento nao da para pesquisar, e criar
                # as cegas geraria um SEGUNDO contato para esta empresa.
                _marcar(db, empresa, status="pendente")
                return
            # Contato sumiu do Tiny: cai no caminho de criacao.

        achado = pesquisar_contato(documento) if documento else tiny.Resultado(ok=False)
        if achado.ok and achado.id:
            _marcar(db, empresa, status="enviada", tiny_id=achado.id)
            return
        if achado.deve_tentar_de_novo:
            _marcar(db, empresa, status="pendente")
            return

        resultado = incluir_contato(tiny.contato_para_criar(empresa))
        if resultado.duplicidade and documento:
            # Rede de seguranca: alguem criou entre a pesquisa e a inclusao.
            achado = pesquisar_contato(documento)
            if achado.ok and achado.id:
                _marcar(db, empresa, status="enviada", tiny_id=achado.id)
                return
        _aplicar(db, empresa, resultado)
    except Exception:  # noqa: BLE001 - best-effort: nunca derruba quem agendou
        try:
            db.rollback()
        except Exception:  # noqa: BLE001 - a sessao pode nao ter transacao aberta
            pass
        logger.exception("falha ao sincronizar a empresa %s com o Tiny", empresa_id)
    finally:
        if propria:
            db.close()


def _aplicar(db, empresa, resultado: tiny.Resultado, *, manter_id: bool = False) -> None:
    if resultado.ok and (manter_id or resultado.id is not None):
        _marcar(db, empresa, status="enviada",
                tiny_id=None if manter_id else resultado.id)
    elif resultado.ok:
        # OK sem id e sem manter: nao ha o que gravar como tiny_id, e "enviada"
        # sem tiny_id nunca mais entraria no caminho de alteracao.
        _marcar(db, empresa, status="pendente")
    elif resultado.deve_tentar_de_novo:
        # Limite ou rede: passa sozinho, entao nao e' erro de dado.
        _marcar(db, empresa, status="pendente")
    else:
        _marcar(db, empresa, status="erro", erro=resultado.mensagem)
