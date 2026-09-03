"""Desfaz a calibracao que OS de MANUTENCAO gravaram no aparelho.

Ate 09/2026 `concluir_laboratorio` espelhava calibracao para QUALQUER OS, sem
olhar o `tipo_servico`. Numa OS tipo 'M' isso renovava `ult_calibragem` e
`prox_calibragem` do aparelho com a data da manutencao: a proxima calibracao era
empurrada (o aparelho aparecia "em dia" alem do que vale) e a garantia que mudava
era a de calibracao, nao a de manutencao — foi o chamado do laboratorio na
OS 11166 / caixa 997, em 03/09/2026. O guard entrou junto com este script.

CRITERIO: OS tipo 'M' com o laboratorio concluido cujo aparelho ainda esta com
`ult_calibragem` IGUAL a data dessa OS. Igualdade exata, entao aparelho que ja
foi recalibrado depois nao e tocado, e rodar de novo depois de aplicar nao acha
mais nada — idempotente.

NEM TODA OS 'M' e manutencao pura. Algumas foram tipadas errado e calibraram de
fato: o script SO mexe nas que nao tem nenhum sinal de calibracao (sem
`calib_cert` e sem certificado tipo 'C' emitido). As outras ele apenas LISTA —
quem corrige o `tipo_servico` para 'A' e o laboratorio, na tela.

    python -m app.scripts.corrigir_calibracao_de_os_manutencao              # so simula
    python -m app.scripts.corrigir_calibracao_de_os_manutencao --aplicar    # grava
"""
import argparse

from app.core.calibracao import proxima_calibracao
from app.core import os_workflow as wf
from app.models import EquipamentoCliente, Ordem, OSCertificado
from app.models.database import SessionLocal


def _os_suspeitas(db):
    """OS 'M' concluidas no lab cujo aparelho ficou com a data DELAS na calibracao."""
    return (
        db.query(Ordem, EquipamentoCliente)
        .join(EquipamentoCliente, EquipamentoCliente.id == Ordem.equipamento_cliente)
        .filter(
            Ordem.tipo_servico == "M",
            Ordem.desfecho_lab == wf.DESFECHO_CONCLUIDO,
            Ordem.data_calibracao.isnot(None),
            EquipamentoCliente.ult_calibragem.isnot(None),
        )
        .order_by(Ordem.id)
        .all()
    )


def _calibrou_de_fato(db, ordem) -> bool:
    """A OS foi tipada 'M' mas emitiu certificado de calibracao ou preencheu o
    numero dele? Entao a data no aparelho e legitima — nao e nosso caso."""
    if ordem.calib_cert:
        return True
    return (
        db.query(OSCertificado)
        .filter(OSCertificado.os == ordem.id, OSCertificado.tipo == "C")
        .first()
        is not None
    )


def _ultima_calibracao_real(db, equipamento_cliente_id, excluir_os):
    """A OS de calibracao mais recente do aparelho ('C', 'A' ou legado sem tipo).

    Devolve (data, proxima) ou (None, None) quando o aparelho nunca foi calibrado
    pelo sistema — nesse caso a calibracao do cadastro e so o efeito do bug e a
    verdade e nao ter data nenhuma.
    """
    candidatas = (
        db.query(Ordem)
        .filter(
            Ordem.equipamento_cliente == equipamento_cliente_id,
            Ordem.id != excluir_os,
            Ordem.fase != wf.FASE_CANCELADA,
            Ordem.data_calibracao.isnot(None),
            (Ordem.tipo_servico.is_(None)) | (Ordem.tipo_servico.in_(("C", "A"))),
        )
        .order_by(Ordem.data_calibracao.desc())
        .all()
    )
    if not candidatas:
        return None, None
    o = candidatas[0]
    ult = o.data_calibracao.date()
    prox = o.prox_calibragem.date() if o.prox_calibragem is not None else proxima_calibracao(ult)
    return ult, prox


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--aplicar", action="store_true", help="grava de fato (sem isso, so simula)")
    args = p.parse_args()

    db = SessionLocal()
    try:
        corrigir, revisar = [], []
        for ordem, ec in _os_suspeitas(db):
            if ec.ult_calibragem != ordem.data_calibracao.date():
                continue                      # aparelho ja recalibrado depois
            if _calibrou_de_fato(db, ordem):
                revisar.append((ordem, ec))
                continue
            ult, prox = _ultima_calibracao_real(db, ec.id, ordem.id)
            corrigir.append((ordem, ec, ult, prox))

        print(f"APARELHOS a corrigir: {len(corrigir)}")
        for ordem, ec, ult, prox in corrigir:
            destino = f"{ult} / {prox}" if ult else "SEM CALIBRACAO (limpa as duas datas)"
            print(f"   OS #{ordem.id:<6} aparelho #{ec.id:<6} serie={str(ec.serie or '-'):<15} "
                  f"{ec.ult_calibragem} / {ec.prox_calibragem}  ->  {destino}")

        print()
        print(f"OS tipadas 'M' que CALIBRARAM de fato (nao mexer aqui): {len(revisar)}")
        for ordem, ec in revisar:
            print(f"   OS #{ordem.id:<6} aparelho #{ec.id:<6} serie={str(ec.serie or '-'):<15} "
                  f"cert={ordem.calib_cert or '-'}  -> laboratorio deve trocar o tipo para 'Ambas'")

        if not args.aplicar:
            print("\n(simulacao — rode com --aplicar para gravar)")
            return

        for ordem, ec, ult, prox in corrigir:
            ec.ult_calibragem = ult
            ec.prox_calibragem = prox
            # A OS de manutencao tambem nao deve carregar proxima calibracao:
            # a tela da OS a exibe e ela veio do mesmo espelhamento errado.
            ordem.prox_calibragem = None
        db.commit()
        print(f"\ngravado: {len(corrigir)} aparelhos")
    finally:
        db.close()


if __name__ == "__main__":
    main()
