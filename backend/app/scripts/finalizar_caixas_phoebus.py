"""Encerramento administrativo das caixas de Phoebus/Modulo que ja sairam da empresa.

Depois que `mover_phoebus_posvendas` as tirou do Pos-Vendas (18/09/2026), 39 caixas de
Phoebus/Modulo ficaram no Financeiro (fase 10). As que ja foram despachadas nao tem como
ser fechadas pelo fluxo normal: sair da 10 exige NOTA FISCAL e sair da 7 exige
COD_RETORNO, e nenhuma delas tem nem um nem outro (conferido na base: 0 notas, 0
rastreios, `pago=False` em todas). Este script fecha na mao o que a tela nao alcanca.

CRITERIO, igual ao ENC-ADM de 30/07/2026:
  - caixa e OS ativas vao para a fase 8 (Finalizada), `situacao='F'`, `data_retorno=agora`
  - `cod_retorno` recebe o MARCADOR, para conseguir achar (e reverter) essas OS depois
  - NAO marca `pago` nem `aceite`: afirmaria pagamento e aval do cliente que ninguem deu.
    E' o padrao do legado — 1 em 9864 OS finalizadas tem esses campos.
  - OS cancelada (fase 9) nao e' tocada: mantem o vinculo com a caixa, mas nao anda.

Alvo: caixas cujas OS ativas sao TODAS de Phoebus/Modulo e estao na fase 10. Caixa de
aparelho normal no Financeiro tem nota fiscal a receber e segue o fluxo dela, entao nunca
entra aqui — nem se for passada em `--excluir` ao contrario.

SIMULA POR PADRAO. Para gravar: --aplicar

    python -m app.scripts.finalizar_caixas_phoebus --excluir 1051,1049,1047
    python -m app.scripts.finalizar_caixas_phoebus --excluir 1051,1049,1047 --aplicar

Para achar tudo o que esta rodada fez:

    select * from ordens where cod_retorno = 'ENC-ADM-20260918';
"""
import argparse

from sqlalchemy.orm import Session

from app.api.ordens_acoes import agora, registrar_log
from app.core import fluxo_modulo
from app.core import os_workflow as wf
from app.models import Caixa
from app.models.database import SessionLocal

ORIGEM = wf.FASE_FINANCEIRO      # 10
DESTINO = wf.FASE_FINALIZADA     # 8

# Marcador do encerramento, gravado em `ordens.cod_retorno`. E' a unica forma de achar
# essas OS depois — sem ele ficam indistinguiveis de OS fechada pelo fluxo normal.
MARCADOR = "ENC-ADM-20260918"


def _ordens_ativas(caixa: Caixa) -> list:
    return [o for o in caixa.ordens if wf.eh_ativa(o.fase)]


def caixas_alvo(db: Session, *, excluir: set[int]) -> list[Caixa]:
    """Caixas no Financeiro cujas OS ativas sao TODAS de Phoebus/Modulo, menos `excluir`.

    `all`, e nao `caixa_de_modulo` (que e' `any`), pelo mesmo motivo de
    `mover_phoebus_posvendas`: numa caixa mista o aparelho normal seria finalizado
    junto, sem nota e sem rastreio.
    """
    alvo = []
    for cx in db.query(Caixa).filter(Caixa.fase == ORIGEM).order_by(Caixa.id).all():
        if cx.id in excluir:
            continue
        ativas = _ordens_ativas(cx)
        if ativas and all(fluxo_modulo.os_de_modulo(o) for o in ativas):
            alvo.append(cx)
    return alvo


def processar(db: Session, *, excluir: set[int], aplicar: bool) -> dict:
    caixas = caixas_alvo(db, excluir=excluir)
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
        quando = agora()
        for o in ativas:
            o.fase = DESTINO
            o.situacao = "F"
            o.cod_retorno = MARCADOR
            o.data_retorno = quando
            registrar_log(db, o, None,
                          f"Caixa #{cx.id}: {ORIGEM} -> {DESTINO} "
                          f"(encerramento administrativo {MARCADOR}: caixa de "
                          f"Phoebus/Modulo ja despachada, sem nota fiscal e sem rastreio)")
        cx.fase = DESTINO

    if aplicar:
        db.commit()

    return {"caixas": len(caixas), "ordens": total_ordens, "detalhes": detalhes}


def _ids(texto: str) -> set[int]:
    return {int(p) for p in texto.split(",") if p.strip()}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--excluir", type=_ids, default=set(), metavar="IDS",
                    help="ids de caixa a POUPAR, separados por virgula "
                         "(as que ainda estao na empresa)")
    ap.add_argument("--aplicar", action="store_true",
                    help="grava de fato (sem isso, so simula)")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        r = processar(db, excluir=args.excluir, aplicar=args.aplicar)
    finally:
        db.close()

    for d in r["detalhes"]:
        print(f"  caixa {d['caixa']} · {d['cliente'] or '?'} · "
              f"{len(d['ordens'])} OS {d['ordens']} · {ORIGEM} -> {DESTINO}")

    if args.excluir:
        print(f"\nPoupadas ({len(args.excluir)}): {sorted(args.excluir)}")
    print(f"Caixas: {r['caixas']} / OS: {r['ordens']} · marcador {MARCADOR}")
    if args.aplicar:
        print("APLICADO.")
    else:
        print("MODO SIMULACAO — NADA FOI GRAVADO. Rode com --aplicar para valer.")


if __name__ == "__main__":
    main()
