"""Leva ate Finalizada as caixas da carga retroativa de Ganho cujo processo ja
correu por fora do sistema.

Contexto: a integracao GrowthHS -> GestorHS ficou quebrada entre 29/07 e 25/08/2026
(nao havia worker Celery consumindo a fila), entao dezenas de caixas ficaram presas em
Pos-Vendas enquanto o processo real seguia normalmente na empresa — proposta ganha,
nota emitida, aparelho devolvido. A carga retroativa
(hsgrowth: scripts/retroagir_ganho_gestorhs.py --aplicar) traz essas caixas de
Pos-Vendas(6) para Financeiro(10). Este script fecha o resto do caminho:

    Financeiro(10) -> Preparando Retorno(7) -> Finalizada(8)

Reproduz fielmente o que `executar_avanco_caixa` (app/api/caixas.py) faria nos dois
avancos, inclusive os textos de log — a diferenca e' que roda por SQL, em lote.

DECISOES ASSUMIDAS (o Erick confirmou em 25/08/2026):
  - **Nota fiscal dispensada.** Nenhuma das OS tem nota anexada; o proprio sistema
    preve a dispensa pelo Administrador (`sem_nota_fiscal`), e o log carrega essa
    marca, igual ao fluxo normal.
  - **`pago=True`** e' marcado porque o processo financeiro correu por fora. A data
    real do pagamento nao existe em lugar nenhum, entao `data_pagamento` recebe o
    instante desta execucao — o marcador abaixo explica a origem.
  - **`cod_retorno` = ENC-ADM-<data>**, mesma convencao do encerramento em massa de
    30/07/2026, para que essas OS sejam encontraveis depois.

O que NAO faz: nao mexe em `aceite`/`data_aceite` (quem cuida disso e' a carga
retroativa mais o corrigir_data_aceite_retroativo.py) e nao sincroniza o TaskHS —
o drift dos cards e' atualizado a mao, como foi decidido em julho.

SIMULA POR PADRAO. Para gravar: --aplicar

    python -m app.scripts.encerrar_caixas_ganho_retroativo
    python -m app.scripts.encerrar_caixas_ganho_retroativo --aplicar

Escreve com o perfil `admin` do cadastro de bancos — rode no Konsole.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

try:
    import bancos
except ModuleNotFoundError:  # pragma: no cover
    sys.exit(
        "modulo `bancos` nao encontrado. Rode com a venv de ~/projetos/bancos ou "
        "com PYTHONPATH=/home/ericks/projetos/bancos."
    )

# As 53 caixas da carga retroativa MENOS 864, 918 e 919, que seguem o fluxo normal
# e devem permanecer em Financeiro (conferido pelo Erick no TaskHS em 25/08/2026).
CAIXAS = [
    745, 749, 750, 751, 756, 757, 758, 760, 761, 843, 844, 848, 849, 850, 852, 853,
    854, 856, 859, 860, 861, 862, 870, 871, 873, 874, 875, 876, 877, 878, 881, 887,
    889, 890, 893, 894, 896, 897, 898, 905, 906, 911, 912, 914, 915, 917, 921, 923,
    935, 937,
]

FASE_FINANCEIRO, FASE_PREPARANDO, FASE_FINALIZADA = 10, 7, 8
ATIVAS = (4, 5, 6, 10, 7)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--aplicar", action="store_true",
                    help="grava de verdade (sem a flag, so simula e faz rollback)")
    args = ap.parse_args()

    agora = datetime.now(timezone.utc)
    marcador = f"ENC-ADM-{agora:%Y%m%d}"
    nota = "(sem nota fiscal, dispensada pelo Administrador)"

    print()
    print("=" * 78)
    print("  APLICANDO" if args.aplicar else "  SIMULACAO (nada sera gravado)")
    print("=" * 78)
    print(f"  caixas alvo: {len(CAIXAS)}   marcador: {marcador}")
    print()

    with bancos.conectar("gestorhs", perfil="admin") as conexao:
        with conexao.cursor() as cur:
            cur.execute(
                "select id, fase from caixas where id = any(%s) order by id", (CAIXAS,))
            estado = dict(cur.fetchall())

            prontas = [c for c, f in estado.items() if f == FASE_FINANCEIRO]
            fora = {c: f for c, f in estado.items() if f != FASE_FINANCEIRO}
            sumiu = [c for c in CAIXAS if c not in estado]

            if fora:
                print("  FORA DE FINANCEIRO — nao serao tocadas:")
                for c, f in sorted(fora.items()):
                    motivo = "ainda em Pos-Vendas (rode a carga retroativa antes)" if f == 6 else f"fase {f}"
                    print(f"    caixa {c}: {motivo}")
                print()
            if sumiu:
                print(f"  NAO EXISTEM: {sumiu}\n")
            if not prontas:
                sys.exit("  Nenhuma caixa em Financeiro(10). Rode a carga retroativa primeiro.\n")

            cur.execute(
                "select id, caixa from ordens where caixa = any(%s) and fase = any(%s) order by caixa, id",
                (prontas, list(ATIVAS)))
            ordens = cur.fetchall()
            print(f"  caixas em Financeiro: {len(prontas)}   OS ativas a encerrar: {len(ordens)}")
            print()

            logs: list[tuple] = []
            for os_id, caixa in ordens:
                # 10 -> 7: paga a OS (nota dispensada) — espelha executar_avanco_caixa
                cur.execute(
                    "update ordens set pago = true, data_pagamento = %s, fase = %s where id = %s",
                    (agora, FASE_PREPARANDO, os_id))
                logs.append((os_id, agora, "1",
                             f"Caixa #{caixa}: {FASE_FINANCEIRO} -> {FASE_PREPARANDO} {nota}"
                             f" - encerramento administrativo {agora:%Y-%m-%d}"))
                # 7 -> 8: finaliza com o marcador no lugar do codigo de retorno real
                cur.execute(
                    "update ordens set cod_retorno = %s, data_retorno = %s, situacao = 'F', "
                    "fase = %s where id = %s",
                    (marcador, agora, FASE_FINALIZADA, os_id))
                logs.append((os_id, agora, "1",
                             f"Caixa #{caixa}: {FASE_PREPARANDO} -> {FASE_FINALIZADA}"
                             f" - encerramento administrativo {agora:%Y-%m-%d}"))

            cur.executemany(
                "insert into logs_os (os, usuario, datalog, autor, texto) "
                "values (%s, null, %s, %s, %s)", logs)
            cur.execute("update caixas set fase = %s where id = any(%s)",
                        (FASE_FINALIZADA, prontas))

            for caixa in sorted(prontas):
                qtd = sum(1 for _, c in ordens if c == caixa)
                print(f"  caixa {caixa:<5} -> Finalizada  ({qtd} OS)")

            print()
            print(f"  caixas: {len(prontas)}   OS: {len(ordens)}   logs: {len(logs)}")

            if args.aplicar:
                conexao.commit()
                print(f"\n  GRAVADO. Para achar depois: cod_retorno = '{marcador}'\n")
            else:
                conexao.rollback()
                print("\n  Nada gravado (rollback). Para aplicar: --aplicar\n")


if __name__ == "__main__":
    main()
