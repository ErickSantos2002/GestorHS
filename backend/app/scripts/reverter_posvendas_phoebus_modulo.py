"""Devolve ao Pos-Vendas as caixas de Phoebus+Modulo que o backfill levou ao Financeiro.

`mover_phoebus_posvendas` rodou em 18/09/2026 com o criterio largo (`any` de
Phoebus/Modulo) e moveu 39 caixas de 6 -> 10. Pela regra correta — so a caixa 100%
Modulo pula o Pos-Vendas — 7 delas nao deviam ter saido: 1003, 1011, 1028, 1030, 1043,
1047 e 1049, todas Phoebus+Modulo. No TaskHS os cards dessas 7 estao parados em
"LIBERADOS DO LABORATORIO" (lista 202), antes ainda de "Servicos" (203): elas nao
passaram por servico nem pelo comercial.

CRITERIO (triplice, auto-limitante):
  - caixa na fase 10 (Financeiro), E
  - com o log do backfill em alguma OS dela (MARCA_BACKFILL), E
  - `not fluxo_modulo.caixa_pula_posvendas(ativas)` — a regra nova diz que ela nao
    devia ter desviado.

RECUSA O LOTE INTEIRO se achar `aceite`, `pago` ou nota fiscal em qualquer caixa alvo:
seria caixa que o Financeiro ja trabalhou, e voltar ao Pos-Vendas desfaria o trabalho.
Conferido em 18/09/2026: as 7 estao zeradas nos cinco campos.

NAO fala com TaskHS nem GrowthHS: essas caixas nunca tiveram card espelhado (o gate de
modulo bloqueia), e os cards que existem no board foram feitos a mao.

As 6 caixas de Phoebus+Modulo ja fechadas pelo ENC-ADM-20260918 NAO sao tocadas: estao
na fase 8, ja foram despachadas e o cliente recebeu.

SIMULA POR PADRAO. Para gravar: --aplicar

    python -m app.scripts.reverter_posvendas_phoebus_modulo
    python -m app.scripts.reverter_posvendas_phoebus_modulo --aplicar

Para achar o que esta rodada fez:

    select * from logs_os where texto like '%10 -> 6 (Phoebus%';
"""
import argparse

from sqlalchemy.orm import Session

from app.api.ordens_acoes import registrar_log
from app.core import fluxo_modulo
from app.core import os_workflow as wf
from app.models import Caixa, LogOS, NotaFiscal
from app.models.database import SessionLocal

ORIGEM = wf.FASE_FINANCEIRO     # 10
DESTINO = wf.FASE_POSVENDAS     # 6

# Trecho do log gravado por `mover_phoebus_posvendas`. E' o que amarra o alvo AQUELE
# lote, e nao a qualquer caixa que tenha chegado ao Financeiro por conta propria.
MARCA_BACKFILL = "nao passa por Pos-Vendas"


class LoteSujo(Exception):
    """Alguma caixa alvo ja foi trabalhada pelo Financeiro. Nada e' gravado."""


def _ordens_ativas(caixa: Caixa) -> list:
    return [o for o in caixa.ordens if wf.eh_ativa(o.fase)]


def _veio_do_backfill(db: Session, caixa: Caixa) -> bool:
    ids = [o.id for o in caixa.ordens]
    if not ids:
        return False
    return db.query(LogOS).filter(
        LogOS.os.in_(ids), LogOS.texto.like(f"%{MARCA_BACKFILL}%")).first() is not None


def caixas_alvo(db: Session) -> list[Caixa]:
    """Caixas do backfill que, pela regra nova, nao deviam ter saido do Pos-Vendas."""
    alvo = []
    for cx in db.query(Caixa).filter(Caixa.fase == ORIGEM).order_by(Caixa.id).all():
        ativas = _ordens_ativas(cx)
        if not ativas or fluxo_modulo.caixa_pula_posvendas(ativas):
            continue
        if _veio_do_backfill(db, cx):
            alvo.append(cx)
    return alvo


def conferir(db: Session, caixas: list[Caixa]) -> list[str]:
    """Motivos para NAO reverter. Lista vazia = lote limpo."""
    problemas = []
    for cx in caixas:
        for o in _ordens_ativas(cx):
            if o.aceite:
                problemas.append(f"caixa {cx.id}: OS {o.id} ja tem aceite")
            if o.pago:
                problemas.append(f"caixa {cx.id}: OS {o.id} ja esta paga")
            if o.nota_fiscal:
                problemas.append(f"caixa {cx.id}: OS {o.id} tem nota fiscal legada")
        if db.query(NotaFiscal).filter(NotaFiscal.caixa == cx.id).first() is not None:
            problemas.append(f"caixa {cx.id}: ja tem nota fiscal anexada")
    return problemas


def processar(db: Session, *, aplicar: bool) -> dict:
    """Devolve as caixas alvo ao Pos-Vendas. Sem `aplicar`, so conta e descreve."""
    caixas = caixas_alvo(db)
    problemas = conferir(db, caixas)
    if problemas:
        raise LoteSujo("; ".join(problemas))

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
                          f"(Phoebus+Modulo passa pelo Pos-Vendas: reversao do "
                          f"backfill de 18/09/2026)")
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
    except LoteSujo as e:
        print(f"RECUSADO, nada foi gravado: {e}")
        raise SystemExit(1)
    finally:
        db.close()

    for d in r["detalhes"]:
        print(f"  caixa {d['caixa']:>5}  {len(d['ordens'])} OS  {d['cliente'] or '?'}")
    acao = "revertidas" if args.aplicar else "a reverter (SIMULACAO)"
    print(f"\n{r['caixas']} caixas / {r['ordens']} OS {acao}: {ORIGEM} -> {DESTINO}")
    if not args.aplicar:
        print("Rode de novo com --aplicar para gravar.")


if __name__ == "__main__":
    main()
