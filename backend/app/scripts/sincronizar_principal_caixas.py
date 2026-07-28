"""Backfill ONE-TIME: corrige `cliente_principal` de caixas existentes cujo valor
esta NULO ou desatualizado (caixas abertas antes do auto-set da abertura/vinculo, ou
que ficaram com o valor antigo apos um desvinculo).

Uso: python -m app.scripts.sincronizar_principal_caixas [--aplicar]

DRY-RUN POR PADRAO — sem `--aplicar` so IMPRIME o que mudaria, sem tocar no banco
(nem `db.commit()`, nem atribuir `cx.cliente_principal` em memoria). So grava com
`--aplicar` explicito, porque o alvo aqui e' o Postgres real (DATABASE_URL do .env),
sem confirmacao interativa.

So mexe em caixa cujas OS ATIVAS (`wf.ATIVAS`) tem um UNICO cliente distinto
(`cliente_unico`, do core/caixa.py) — a mesma regra do 2+ usada no auto-set: caixa com
2+ clientes diferentes exige escolha manual e este script nunca decide por ela.
"""
import argparse

from app.core import os_workflow as wf
from app.core.caixa import cliente_unico
from app.models import Caixa, Cliente, Ordem
from app.models.database import SessionLocal


def principal_alvo(db, cx: Caixa) -> int | None:
    """O cliente-alvo da caixa: o unico cliente distinto entre as OS ativas, ou None
    (caixa sem OS ativa, ou com 2+ clientes distintos — nao decide por ela)."""
    clientes = [
        c for (c,) in db.query(Ordem.cliente)
        .filter(Ordem.caixa == cx.id, Ordem.fase.in_(wf.ATIVAS))
        .all()
    ]
    return cliente_unico(clientes)


def main(aplicar: bool) -> None:
    db = SessionLocal()
    try:
        mudancas = []  # (caixa_id, principal_antigo, principal_novo)
        for cx in db.query(Caixa).filter(Caixa.fase.in_(list(wf.ATIVAS))).all():
            alvo = principal_alvo(db, cx)
            if alvo is not None and cx.cliente_principal != alvo:
                mudancas.append((cx.id, cx.cliente_principal, alvo))
                if aplicar:
                    cx.cliente_principal = alvo

        if mudancas:
            nomes = {
                c.id: c.nome
                for c in db.query(Cliente)
                .filter(Cliente.id.in_({novo for _, _, novo in mudancas}))
                .all()
            }
            for cid, antigo, novo in mudancas:
                print(f"CX {cid}: principal {antigo} -> {novo} ({nomes.get(novo, '?')})")

        print(f"{len(mudancas)} caixa(s) {'ATUALIZADA(S)' if aplicar else 'mudariam (dry-run)'}")

        if aplicar:
            db.commit()
        else:
            print("MODO DRY-RUN — NADA FOI GRAVADO. Rode com --aplicar para valer.")
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Backfill do cliente_principal em caixas existentes (dry-run por padrao)."
    )
    ap.add_argument("--aplicar", action="store_true",
                     help="grava as mudancas no banco (padrao: dry-run, so imprime)")
    main(ap.parse_args().aplicar)
