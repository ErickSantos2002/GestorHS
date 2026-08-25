"""Devolve a data real de aceite as OS movidas pela carga retroativa de Ganho.

Quando a caixa avanca de Pos-Vendas(6) para Financeiro(10), o GestorHS marca
`aceite=True` e `data_aceite=agora()` em todas as OS ativas da caixa
(app/api/caixas.py). Numa carga retroativa isso e' um efeito colateral indesejado:
dezenas de OS ficam com a data de aceite do DIA DA CARGA, e nao do dia em que o
negocio foi de fato ganho no GrowthHS.

Este script devolve a data verdadeira, lida do proprio GrowthHS: o evento
`card_won` em `service_card_activities`. Esse `created_at` e' naive em **UTC**
(TimestampMixin usa `datetime.utcnow`), e o `data_aceite` do GestorHS e' timestamptz
tambem em UTC (`agora()` = `datetime.now(timezone.utc)`) — a conversao e' so
carimbar o fuso, sem deslocamento.

SIMULA POR PADRAO. Para gravar: --aplicar

    python -m app.scripts.corrigir_data_aceite_retroativo
    python -m app.scripts.corrigir_data_aceite_retroativo --aplicar

A escrita usa o perfil `admin` do cadastro de bancos (~/.config/bancos/admin.toml),
entao rode no Konsole — nao pela sessao do Claude.

Seguranca:
  - so mexe em OS cuja caixa tem card de Ganho no GrowthHS;
  - so mexe em `data_aceite` carimbado a partir de --desde (padrao: hoje 00:00 UTC),
    ou seja, so o que a carga escreveu — aceites antigos e legitimos ficam intactos;
  - so grava se a data real for ANTERIOR a atual (uma carga sempre carimba depois);
  - roda tudo em uma transacao; sem --aplicar, faz rollback.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone

try:
    import bancos
except ModuleNotFoundError:  # pragma: no cover
    sys.exit(
        "modulo `bancos` nao encontrado. Rode com a venv de ~/projetos/bancos ou "
        "com PYTHONPATH=/home/ericks/projetos/bancos."
    )


SQL_GANHOS = """
    select c.external_id, min(a.created_at) as ganho_em
    from service_cards c
    join service_lists l on l.id = c.list_id
    join service_card_activities a
      on a.service_card_id = c.id and a.activity_type = 'card_won'
    where c.external_source = 'gestorhs.os'
      and c.external_id is not null
      and c.is_deleted = false
      and (l.is_done_stage = true or lower(l.name) like '%ganho%')
    group by c.external_id
"""

SQL_ALVOS = """
    select o.id, o.caixa, o.data_aceite
    from ordens o
    where o.caixa = any(%s)
      and o.aceite is true
      and o.data_aceite >= %s
    order by o.caixa, o.id
"""


def datas_reais_por_caixa() -> dict[int, datetime]:
    """caixa_id -> instante do Ganho no GrowthHS (UTC, tz-aware)."""
    linhas = bancos.consultar("hsgrowth", SQL_GANHOS)
    datas: dict[int, datetime] = {}
    for external_id, ganho_em in zip(linhas["external_id"], linhas["ganho_em"]):
        try:
            caixa = int(str(external_id).strip())
        except (TypeError, ValueError):
            continue  # cards legados guardam o numero da OS, nao o id da caixa
        if ganho_em is None:
            continue
        quando = ganho_em.to_pydatetime() if hasattr(ganho_em, "to_pydatetime") else ganho_em
        if quando.tzinfo is None:
            quando = quando.replace(tzinfo=timezone.utc)
        datas[caixa] = quando
    return datas


def _diferenca(delta: timedelta) -> str:
    """'3d 4h' / '21h' — dias sozinhos escondem uma correcao de quase um dia."""
    horas_totais = int(delta.total_seconds() // 3600)
    dias, horas = divmod(horas_totais, 24)
    return f"{dias}d {horas}h" if dias else f"{horas}h"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--aplicar", action="store_true",
                    help="grava de verdade (sem a flag, so simula e faz rollback)")
    ap.add_argument("--desde", default=None, metavar="YYYY-MM-DD",
                    help="so corrige aceites carimbados a partir desta data "
                         "(UTC; padrao: hoje 00:00)")
    args = ap.parse_args()

    if args.desde:
        try:
            corte = datetime.strptime(args.desde, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            sys.exit("--desde precisa ser no formato YYYY-MM-DD")
    else:
        agora = datetime.now(timezone.utc)
        corte = agora.replace(hour=0, minute=0, second=0, microsecond=0)

    datas = datas_reais_por_caixa()
    if not datas:
        sys.exit("nenhum card de Ganho encontrado no GrowthHS — nada a fazer.")

    print()
    print("=" * 78)
    print("  APLICANDO" if args.aplicar else "  SIMULACAO (nada sera gravado)")
    print("=" * 78)
    print(f"  caixas com Ganho no GrowthHS: {len(datas)}")
    print(f"  corrige data_aceite a partir de: {corte:%Y-%m-%d %H:%M} UTC")
    print()

    caixas = sorted(datas)
    corrigir: list[tuple[datetime, int]] = []
    ignorados = 0

    with bancos.conectar("gestorhs", perfil="admin") as conexao:
        with conexao.cursor() as cur:
            cur.execute(SQL_ALVOS, (caixas, corte))
            alvos = cur.fetchall()

            print(f"  OS com aceite carimbado no periodo: {len(alvos)}")
            print()
            for os_id, caixa, atual in alvos:
                real = datas.get(caixa)
                if real is None or real >= atual:
                    # A data real tem que ser anterior — se nao for, algo nao bate
                    # com a premissa e e' mais seguro nao tocar.
                    ignorados += 1
                    continue
                corrigir.append((real, os_id))
                print(f"  OS {os_id:<7} caixa {caixa:<5} "
                      f"{atual:%d/%m %H:%M} -> {real:%d/%m %H:%M}  "
                      f"(adianta {_diferenca(atual - real)})")

            print()
            print(f"  a corrigir: {len(corrigir)}   ignoradas: {ignorados}")

            if not corrigir:
                print("\n  Nada a fazer.\n")
                return

            cur.executemany("update ordens set data_aceite = %s where id = %s", corrigir)

            if args.aplicar:
                conexao.commit()
                print(f"\n  GRAVADO: {len(corrigir)} OS corrigidas.\n")
            else:
                conexao.rollback()
                print("\n  Nada gravado (rollback). Para aplicar: --aplicar\n")


if __name__ == "__main__":
    main()
