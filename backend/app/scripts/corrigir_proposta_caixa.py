"""Aponta a caixa para a proposta certa quando o Ganho do GrowthHS trouxe o numero errado.

O numero da proposta e' digitado a mao no Resumo do card do GrowthHS
(`business_info.proposal_number`) e o inbound `/integracao/growthhs/caixas/{id}/ganho`
grava em `caixas.numero_proposta` sem conferir de quem e' a proposta. Em 16/09/2026 a
caixa 979 (UNIVALE) recebeu o numero 232 — proposta da MARINGA FERRO-LIGA. A tela da
caixa passou a exibir a proposta da Maringa com o botao "Marcar como Faturada" e o
Financeiro faturou as duas no dia 17/09.

Este script faz a conferencia que faltou: so aceita proposta do MESMO cliente da caixa
(principal ou de alguma OS). A regra vive em `app.core.proposta_caixa`, compartilhada com
`PUT /caixas/{id}/proposta` — o botao "Trocar proposta" da tela da caixa, que ja
reespelha o card do TaskHS. Prefira a tela; o script fica para caixa finalizada ou
sem bloco de proposta.

SIMULA POR PADRAO. Para gravar: --aplicar

    python -m app.scripts.corrigir_proposta_caixa --caixa 979 --proposta 289
    python -m app.scripts.corrigir_proposta_caixa --caixa 979 --proposta 289 --aplicar

`--desfaturar-anterior` desfaz tambem a marcacao de faturada da proposta que estava no
lugar errado. Use so quando ela foi faturada POR ENGANO atraves desta caixa: a proposta
pertence a outro cliente e nao tem nota fiscal propria. E' o equivalente ao botao
"Desfazer faturamento" da tela de Propostas, restrito ao Administrador.

Depois de aplicar, atualize o card do TaskHS — a obs3 mostra "Proposta #N":

    python -m app.scripts.sincronizar_taskhs_caixas --caixas 979 --aplicar

E corrija o `proposal_number` no Resumo do card do GrowthHS, senao um novo Ganho
reescreve o numero errado por cima.
"""
import argparse

from app.models import Caixa, Cliente, Proposta
from app.models.database import SessionLocal
from app.core.proposta_caixa import clientes_da_caixa, conferir  # noqa: F401 (reexportados)


def _descrever(db, numero: int | None) -> str:
    if numero is None:
        return "(nenhuma)"
    p = db.query(Proposta).filter(Proposta.numero == numero).one_or_none()
    if p is None:
        return f"#{numero} (nao existe)"
    nome = "?"
    if p.cliente is not None:
        c = db.query(Cliente).filter(Cliente.id == p.cliente).one_or_none()
        nome = c.nome if c else f"cliente {p.cliente}"
    faturada = " · FATURADA" if p.faturada else ""
    return f"#{numero} — {nome}{faturada}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--caixa", type=int, required=True, help="id da caixa")
    ap.add_argument("--proposta", type=int, required=True, help="NUMERO da proposta correta")
    ap.add_argument("--desfaturar-anterior", action="store_true",
                    help="desfaz a marcacao de faturada da proposta que estava errada")
    ap.add_argument("--aplicar", action="store_true", help="grava de fato (sem isso, so simula)")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        cx = db.query(Caixa).filter(Caixa.id == args.caixa).one_or_none()
        if cx is None:
            print(f"caixa {args.caixa} nao encontrada")
            return
        nova = db.query(Proposta).filter(Proposta.numero == args.proposta).one_or_none()
        if nova is None:
            print(f"proposta {args.proposta} nao encontrada")
            return

        anterior_num = cx.numero_proposta
        print(f"caixa {cx.id} · fase {cx.fase}")
        print(f"  ANTES:  {_descrever(db, anterior_num)}")
        print(f"  DEPOIS: {_descrever(db, args.proposta)}")

        if anterior_num == args.proposta:
            print("\nja esta correto — nada a fazer")
            return

        motivo = conferir(cx, nova)
        if motivo:
            print(f"\nRECUSADO: {motivo}")
            return

        anterior = (db.query(Proposta).filter(Proposta.numero == anterior_num).one_or_none()
                    if anterior_num is not None else None)
        desfaturar: Proposta | None = None
        if args.desfaturar_anterior:
            if anterior is None:
                print("\n--desfaturar-anterior: nao ha proposta anterior")
            elif not anterior.faturada:
                print(f"\n--desfaturar-anterior: proposta {anterior.numero} nao esta faturada")
            elif anterior.cliente in clientes_da_caixa(cx):
                print(f"\n--desfaturar-anterior: proposta {anterior.numero} e' do MESMO cliente "
                      "da caixa — pode ter sido faturada de proposito, nao vou desfazer")
            else:
                desfaturar = anterior
                print(f"\n  desfaturar: #{anterior.numero} "
                      f"(era faturada por {anterior.faturada_por} em {anterior.faturada_em})")

        if not args.aplicar:
            print("\n(simulacao — rode com --aplicar para gravar)")
            return

        cx.numero_proposta = args.proposta
        if desfaturar is not None:
            desfaturar.faturada = False
            desfaturar.faturada_em = None
            desfaturar.faturada_por = None
        db.commit()
        db.refresh(cx)
        print(f"\ngravado: caixa {cx.id} -> proposta {cx.numero_proposta}")
        if desfaturar is not None:
            print(f"gravado: proposta {desfaturar.numero} nao esta mais faturada")
        print(f"\nagora rode: python -m app.scripts.sincronizar_taskhs_caixas "
              f"--caixas {cx.id} --aplicar")
    finally:
        db.close()


if __name__ == "__main__":
    main()
