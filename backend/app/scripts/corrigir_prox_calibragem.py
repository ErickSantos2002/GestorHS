"""Recalcula a proxima calibracao que ficou obsoleta desde o go-live.

Ate 08/2026 nada no GestorHS preenchia `ordens.prox_calibragem` — o sistema
antigo calculava, o novo herdou a coluna e nunca a alimentou. Como o
espelhamento so grava esse campo quando a OS o traz, o aparelho recem-calibrado
seguia com a data do ciclo ANTERIOR e aparecia como "Vencido" (aparelho 7912 /
OS 10905). O calculo automatico entrou em v1.41.0; este script conserta o que
ficou para tras.

CRITERIO: `prox_calibragem <= ult_calibragem`. Uma proxima calibracao que nao e
posterior a ultima esta necessariamente obsoleta — nao existe caso legitimo — e
por isso o script nao toca em nenhuma data plausivel. Aparelho calibrado ha mais
de um ano continua vencido depois da correcao, so que com a data certa.

    python -m app.scripts.corrigir_prox_calibragem              # so simula
    python -m app.scripts.corrigir_prox_calibragem --aplicar    # grava
"""
import argparse

from app.core.calibracao import proxima_calibracao
from app.models import EquipamentoCliente, Ordem
from app.models.database import SessionLocal


def _aparelhos_afetados(db):
    return (
        db.query(EquipamentoCliente)
        .filter(
            EquipamentoCliente.ult_calibragem.isnot(None),
            EquipamentoCliente.prox_calibragem.isnot(None),
            EquipamentoCliente.prox_calibragem <= EquipamentoCliente.ult_calibragem,
        )
        .order_by(EquipamentoCliente.id)
        .all()
    )


def _ordens_afetadas(db):
    """OS ja concluidas no lab e sem a proxima calibracao.

    Nao muda status de nada — a coluna da OS so alimenta a exibicao "Proxima
    calibracao" na tela. Sem isso a tela da OS segue em branco enquanto o
    aparelho mostra a data, que e' a divergencia que gerou o chamado.
    """
    return (
        db.query(Ordem)
        .filter(
            Ordem.desfecho_lab == "concluido",
            Ordem.data_calibracao.isnot(None),
            Ordem.prox_calibragem.is_(None),
        )
        .order_by(Ordem.id)
        .all()
    )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--aplicar", action="store_true", help="grava de fato (sem isso, so simula)")
    p.add_argument("--limite-amostra", type=int, default=10, help="quantas linhas detalhar")
    args = p.parse_args()

    db = SessionLocal()
    try:
        aparelhos = _aparelhos_afetados(db)
        ordens = _ordens_afetadas(db)

        print(f"APARELHOS com proxima calibracao obsoleta: {len(aparelhos)}")
        ativos = sum(1 for ec in aparelhos if ec.ativo)
        print(f"   ativos: {ativos}   inativos: {len(aparelhos) - ativos}")
        for ec in aparelhos[: args.limite_amostra]:
            novo = proxima_calibracao(ec.ult_calibragem)
            print(f"   #{ec.id:<6} serie={str(ec.serie or '-'):<12} "
                  f"calibrado={ec.ult_calibragem}  {ec.prox_calibragem} -> {novo}")
        if len(aparelhos) > args.limite_amostra:
            print(f"   ... e mais {len(aparelhos) - args.limite_amostra}")

        print()
        print(f"OS concluidas sem a proxima calibracao (so exibicao): {len(ordens)}")

        if not args.aplicar:
            print("\n(simulacao — rode com --aplicar para gravar)")
            return

        for ec in aparelhos:
            ec.prox_calibragem = proxima_calibracao(ec.ult_calibragem)
        for o in ordens:
            prox = proxima_calibracao(o.data_calibracao.date())
            if prox is not None:
                o.prox_calibragem = o.data_calibracao.replace(
                    year=prox.year, month=prox.month, day=prox.day
                )
        db.commit()
        print(f"\ngravado: {len(aparelhos)} aparelhos e {len(ordens)} OS")
    finally:
        db.close()


if __name__ == "__main__":
    main()
