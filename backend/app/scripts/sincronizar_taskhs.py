"""Backfill: espelha no TaskHS as OS já existentes (fases ativas + Finalizada).

Uso: python -m app.scripts.sincronizar_taskhs
Idempotente — pode rodar quantas vezes quiser.
"""
from sqlalchemy.orm import Session

from app.core import taskhs
from app.core import os_workflow as wf
from app.integrations import taskhs_client
from app.models import Ordem
from app.models.database import SessionLocal

FASES_BACKFILL = list(wf.ATIVAS) + [wf.FASE_FINALIZADA]


def sincronizar(db: Session) -> tuple[int, int]:
    """Faz upsert de cada OS em fases ativas + Finalizada. Retorna (enviadas, total)."""
    if not taskhs_client.integracao_ativa():
        raise RuntimeError(
            "Integração desligada: configure TASKHS_BASE_URL e TASKHS_API_KEY."
        )
    ordens = (
        db.query(Ordem)
        .filter(Ordem.fase.in_(FASES_BACKFILL))
        .order_by(Ordem.id)
        .all()
    )
    enviadas = 0
    for o in ordens:
        lista = taskhs.lista_da_fase(o.fase)
        if lista is None:
            continue
        try:
            taskhs_client.espelhar_os(o, lista=lista, arquivado=False)
            enviadas += 1
            print(f"OK   OS #{o.id} -> {lista}")
        except Exception as e:  # noqa: BLE001 — relatório, segue para a próxima
            print(f"ERRO OS #{o.id}: {e}")
    return enviadas, len(ordens)


def main() -> None:
    db = SessionLocal()
    try:
        enviadas, total = sincronizar(db)
        print(f"\n{enviadas}/{total} OS sincronizadas com o TaskHS.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
