"""Reenvia ao TaskHS o card de OS especificas (uso pontual).

Util quando um upsert falhou pontualmente — por exemplo depois de uma mudanca
nos `list_id` das listas, que faz o TaskHS responder 404 e o card nao chegar.

Uso:
    python -m app.scripts.reenviar_os_taskhs 10838 10839 10840             # SIMULA (padrao)
    python -m app.scripts.reenviar_os_taskhs 10838 10839 10840 --enviar    # envia de verdade

NAO envia nada sem `--enviar`. Idempotente: a identidade do card e
(source, external_id), entao reenviar atualiza o mesmo card e nunca duplica.
"""
import sys

from sqlalchemy.orm import Session

from app.api import espelhamento
from app.core import taskhs
from app.core.config import settings
from app.integrations import taskhs_client
from app.models import Ordem
from app.models.database import SessionLocal


def _resumo_obs(payload: dict) -> str:
    preenchidas = [k for k in ("obs1", "obs2", "obs3", "obs4", "obs5", "obs6") if payload.get(k)]
    return ", ".join(preenchidas) or "(nenhuma)"


def reenviar(db: Session, ids: list[int], *, enviar: bool) -> tuple[int, int]:
    """Reenvia o card de cada OS informada. Retorna (ok, total_processadas)."""
    if not taskhs_client.integracao_ativa():
        raise RuntimeError(
            "Integração desligada: configure TASKHS_BASE_URL e TASKHS_API_KEY."
        )
    print(f"TaskHS: {settings.TASKHS_BASE_URL}")
    print(f"Modo:   {'ENVIO REAL' if enviar else 'SIMULACAO (use --enviar para valer)'}\n")

    ok = 0
    for oid in ids:
        ordem = db.query(Ordem).filter(Ordem.id == oid).first()
        if ordem is None:
            print(f"ERRO OS #{oid}: nao encontrada")
            continue
        list_id = taskhs.list_id_da_fase(ordem.fase)
        if list_id is None:
            print(f"PULA OS #{oid}: fase {ordem.fase} nao tem lista (cancelada/desconhecida)")
            continue
        payload = espelhamento._montar_payload_os(
            db, ordem, list_id=list_id, arquivado=False
        )
        print(f"OS #{oid}: fase={ordem.fase} -> list_id={list_id} | "
              f"titulo={payload['title']!r} | obs: {_resumo_obs(payload)}")
        if not enviar:
            ok += 1
            continue
        try:
            taskhs_client.enviar_card_sync(payload)
            print(f"  OK enviado")
            ok += 1
        except Exception as e:  # noqa: BLE001 — relatorio, segue para a proxima
            print(f"  ERRO ao enviar: {e}")
    return ok, len(ids)


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--enviar"]
    enviar = "--enviar" in sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    try:
        ids = [int(a) for a in args]
    except ValueError:
        print(f"IDs invalidos: {args}")
        sys.exit(1)

    db = SessionLocal()
    try:
        ok, total = reenviar(db, ids, enviar=enviar)
        rotulo = "enviadas" if enviar else "simuladas"
        print(f"\n{ok}/{total} OS {rotulo}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
