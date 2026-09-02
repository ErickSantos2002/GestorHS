"""Sincroniza no TaskHS os cards das CAIXAS indicadas, na lista da fase atual.

Existe por causa de um efeito colateral do encerramento em lote: quando uma caixa
avanca pela API, o TaskHS e' atualizado junto (`agendar_espelhamento_caixa`). Quando
o avanco e' feito por SQL — como no encerramento da carga retroativa de Ganho de
25/08/2026 — o banco anda e o card do TaskHS fica para tras, parado na lista antiga.

Toca so nas caixas que voce mandar — de proposito: um backfill geral mexeria tambem
nas que ficaram desatualizadas por decisao, como no encerramento administrativo de
30/07. E' o unico caminho de reenvio ao TaskHS desde set/2026, quando os scripts por
OS (`sincronizar_taskhs`, `reenviar_os_taskhs`) sairam junto com o card por OS.

A lista de destino sai da fase ATUAL de cada caixa (`taskhs.list_id_da_fase`), entao
o script serve para qualquer correcao de drift, nao so para esse encerramento:

    4 -> 196 Expedicao   5 -> 197 Laboratorio   6 -> 202 Liberados do Lab
    10 -> 205 Financeiro  7 -> 209 Preparando    8 -> 210 Correios

SIMULA POR PADRAO. Para enviar: --aplicar

    python -m app.scripts.sincronizar_taskhs_caixas --cod-retorno ENC-ADM-20260825
    python -m app.scripts.sincronizar_taskhs_caixas --cod-retorno ENC-ADM-20260825 --aplicar
    python -m app.scripts.sincronizar_taskhs_caixas --caixas 745,749,750 --aplicar

Precisa de TASKHS_BASE_URL/TASKHS_API_KEY de producao — rode DENTRO do container do
GestorHS; o .env local aponta para o TaskHS de desenvolvimento.
"""
import argparse
import sys

from sqlalchemy.orm import Session

from app.api import espelhamento
from app.core import taskhs
from app.integrations import taskhs_client
from app.models import Caixa, Ordem
from app.models.database import SessionLocal


def caixas_por_cod_retorno(db: Session, marcador: str) -> list[int]:
    """Ids das caixas cujas OS carregam este cod_retorno (marcador de encerramento)."""
    linhas = (
        db.query(Ordem.caixa)
        .filter(Ordem.cod_retorno == marcador, Ordem.caixa.isnot(None))
        .distinct()
        .all()
    )
    return sorted(c for (c,) in linhas)


def sincronizar(db: Session, caixas_ids: list[int]) -> tuple[int, int]:
    """Faz upsert do card de cada caixa na lista da sua fase atual.

    Devolve (enviadas, encontradas). Caixa inexistente nao entra na conta; caixa sem
    fase mapeada (encerrada, fase NULL) conta como encontrada mas nao enviada.
    """
    if not taskhs_client.integracao_ativa():
        raise RuntimeError(
            "Integração desligada: configure TASKHS_BASE_URL e TASKHS_API_KEY."
        )
    caixas = db.query(Caixa).filter(Caixa.id.in_(caixas_ids)).order_by(Caixa.id).all()
    enviadas = 0
    for cx in caixas:
        list_id = taskhs.list_id_da_fase(cx.fase) if cx.fase is not None else None
        if list_id is None:
            print(f"PULA caixa #{cx.id}: fase {cx.fase} sem lista no board")
            continue
        try:
            if espelhamento.espelhar_caixa_sync(db, cx, list_id=list_id, arquivado=False):
                enviadas += 1
                print(f"OK   caixa #{cx.id} (fase {cx.fase}) -> lista {list_id}")
            else:
                print(f"PULA caixa #{cx.id}: modulo/phoebus tem fluxo proprio")
        except Exception as e:  # noqa: BLE001 — relatório, segue para a próxima
            print(f"ERRO caixa #{cx.id}: {e}")
    return enviadas, len(caixas)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--caixas", help="ids separados por virgula (ex.: 745,749,750)")
    ap.add_argument("--cod-retorno", dest="cod_retorno",
                    help="seleciona as caixas cujas OS tem este cod_retorno")
    ap.add_argument("--aplicar", action="store_true",
                    help="envia de verdade (sem a flag, so lista o que faria)")
    args = ap.parse_args()

    if not args.caixas and not args.cod_retorno:
        ap.error("informe --caixas ou --cod-retorno")

    db = SessionLocal()
    try:
        if args.caixas:
            try:
                ids = [int(p) for p in args.caixas.split(",") if p.strip()]
            except ValueError:
                sys.exit("--caixas aceita so numeros separados por virgula")
        else:
            ids = caixas_por_cod_retorno(db, args.cod_retorno)
            print(f"caixas com cod_retorno={args.cod_retorno}: {len(ids)}")

        if not ids:
            sys.exit("nenhuma caixa selecionada.")

        if not args.aplicar:
            caixas = db.query(Caixa).filter(Caixa.id.in_(ids)).order_by(Caixa.id).all()
            print("\n  SIMULACAO (nada enviado)\n")
            for cx in caixas:
                destino = taskhs.list_id_da_fase(cx.fase) if cx.fase is not None else None
                print(f"  caixa #{cx.id}  fase {cx.fase}  -> lista {destino or '(sem lista)'}")
            print(f"\n  {len(caixas)} caixas. Para enviar: --aplicar\n")
            return

        enviadas, total = sincronizar(db, ids)
        print(f"\n{enviadas}/{total} caixas sincronizadas com o TaskHS.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
