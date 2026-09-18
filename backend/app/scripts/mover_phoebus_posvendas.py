"""Move para o Financeiro as caixas de Phoebus/Modulo que ficaram paradas em Pos-Vendas.

O servico do Phoebus e do Modulo nao passa pelo comercial — desde set/2026 a caixa deles
sai do laboratorio direto para o Financeiro (`os_workflow.PROXIMA_SO_MODULO`). Antes disso
o fluxo era o mesmo de todo mundo e elas caiam na fase 6, onde ninguem tinha o que fazer:
em 18/09/2026 havia 40 caixas / 82 OS empilhadas ali, a maior concentracao delas em
qualquer fase ativa.

Este script e' o acerto de uma vez do que ficou para tras. Ele NAO passa por
`executar_avanco_caixa`: aquele caminho, com origem=6, marcaria `aceite=True` e
`data_aceite` nas 82 OS — exatamente o aval comercial que nao houve e que o fluxo novo
faz questao de nao inventar (das 974 OS de Phoebus/Modulo da base, 962 estao com
`aceite=False`). Aqui o avanco e' escrito a mao: fase da caixa, fase das OS ativas e log.

Espelhamento nao e' chamado de proposito — caixa de modulo nao tem card no TaskHS nem no
GrowthHS (`fluxo_modulo`), entao nao ha nada la fora para atualizar.

SIMULA POR PADRAO. Para gravar: --aplicar

    python -m app.scripts.mover_phoebus_posvendas
    python -m app.scripts.mover_phoebus_posvendas --aplicar

E' idempotente: depois de aplicar, a segunda rodada nao acha mais nada.
"""
import argparse

from sqlalchemy.orm import Session

from app.api.ordens_acoes import registrar_log
from app.core import fluxo_modulo
from app.core import os_workflow as wf
from app.models import Caixa
from app.models.database import SessionLocal

ORIGEM = 6                      # Pos-Vendas
DESTINO = wf.FASE_FINANCEIRO    # 10


def _ordens_ativas(caixa: Caixa) -> list:
    """As OS que andam de fase. Mesmo criterio de `api/caixas.py` — canceladas
    mantem o vinculo com a caixa, mas nao acompanham o avanco."""
    return [o for o in caixa.ordens if wf.eh_ativa(o.fase)]


def caixas_alvo(db: Session) -> list[Caixa]:
    """Caixas em Pos-Vendas cujas OS ativas sao TODAS Modulo.

    Mesmo predicado do avanco em tempo real (`fluxo_modulo.caixa_pula_posvendas`) —
    nao ha mais duas versoes da regra. Ate 18/09/2026 este script usava um `all`
    proprio porque o avanco usava um `any` largo demais; com o criterio corrigido, a
    caixa com Phoebus e a caixa mista caem fora por construcao nos dois caminhos.

    Caixa sem nenhuma OS ativa tambem fica de fora: nao ha o que mover, e adiantar
    so a caixa deixaria uma fase 10 vazia.
    """
    alvo = []
    for cx in db.query(Caixa).filter(Caixa.fase == ORIGEM).order_by(Caixa.id).all():
        if fluxo_modulo.caixa_pula_posvendas(_ordens_ativas(cx)):
            alvo.append(cx)
    return alvo


def processar(db: Session, *, aplicar: bool) -> dict:
    """Move as caixas alvo para o Financeiro. Sem `aplicar`, so conta e descreve."""
    caixas = caixas_alvo(db)
    detalhes = []
    total_ordens = 0

    for cx in caixas:
        ativas = _ordens_ativas(cx)
        total_ordens += len(ativas)
        detalhes.append({
            "caixa": cx.id,
            "ordens": [o.id for o in ativas],
            "cliente": next((o.cliente_nome for o in ativas if o.cliente_nome), None),
        })
        if not aplicar:
            continue
        for o in ativas:
            o.fase = DESTINO
            registrar_log(db, o, None,
                          f"Caixa #{cx.id}: {ORIGEM} -> {DESTINO} "
                          f"(fluxo da caixa 100% Modulo nao passa por Pos-Vendas)")
        cx.fase = DESTINO

    if aplicar:
        db.commit()

    return {"caixas": len(caixas), "ordens": total_ordens, "detalhes": detalhes}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aplicar", action="store_true",
                    help="grava de fato (sem isso, so simula)")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        r = processar(db, aplicar=args.aplicar)
    finally:
        db.close()

    for d in r["detalhes"]:
        cliente = d["cliente"] or "?"
        print(f"  caixa {d['caixa']} · {cliente} · "
              f"{len(d['ordens'])} OS {d['ordens']} · {ORIGEM} -> {DESTINO}")

    print(f"\nCaixas: {r['caixas']} / OS: {r['ordens']}")
    if args.aplicar:
        print("APLICADO.")
    else:
        print("MODO SIMULACAO — NADA FOI GRAVADO. Rode com --aplicar para valer.")


if __name__ == "__main__":
    main()
