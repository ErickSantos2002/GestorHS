"""Resolve patrimonio repetido dentro da frota de um cliente.

Serve para o depois de `unificar_clientes`: juntar dois cadastros junta duas
numeracoes que comecavam em 1, e o cliente fica com dois aparelhos "1", dois "2"
e assim por diante. Foi o caso da FERTILIZANTES TOCANTINS (#1059) em 08/09/2026.

    python -m app.scripts.renumerar_patrimonios --cliente 1059 --aparelhos 4153,5067
    python -m app.scripts.renumerar_patrimonios --cliente 1059 --aparelhos 4153,5067 --aplicar

`--aparelhos` sao os ids de `equipamentos_cliente` que CEDEM o numero — na
unificacao, os que vieram do cadastro absorvido. Quem nao esta na lista nunca
anda: o objetivo e' nao mexer na etiqueta que o cliente ja conhece.

Sem `--aparelhos`, cede quem entrou depois (id maior) em cada grupo repetido.

Da unificacao em diante isso sai de graca: `unificar_clientes
--renumerar-patrimonios` faz o mesmo no mesmo passo, sem precisar montar a lista
de ids a mao.

`patrimonio` sai no certificado pelo token `[patrimonio]`, mas documento ja
emitido fica congelado em `os_certificados` — renumerar nao reescreve o passado.

Idempotente: rodar de novo nao acha mais colisao.
"""
import argparse

from sqlalchemy import text

from app.core.unificacao_cliente import renumerar_patrimonios
from app.models import Cliente, EquipamentoCliente
from app.models.database import SessionLocal


def ler_frota(db, cliente_id) -> list[tuple[int, str]]:
    return [
        (ec.id, ec.patrimonio)
        for ec in db.query(EquipamentoCliente)
        .filter(EquipamentoCliente.cliente == cliente_id)
        .order_by(EquipamentoCliente.id)
        .all()
    ]


def quem_cede_por_padrao(frota) -> set[int]:
    """Sem lista explicita: em cada numero repetido, cede quem entrou depois."""
    por_numero = {}
    for i, p in frota:
        if isinstance(p, str) and p.strip().isdigit():
            por_numero.setdefault(p.strip(), []).append(i)
    return {i for ids in por_numero.values() if len(ids) > 1 for i in sorted(ids)[1:]}


def planejar(db, cliente_id, ceder=None):
    """Devolve (cliente, {ec_id: (serie, de, para)}, recusas)."""
    cliente = db.get(Cliente, cliente_id)
    if cliente is None:
        return None, {}, [f"cliente #{cliente_id} nao existe"]

    frota = ler_frota(db, cliente_id)
    conhecidos = {i for i, _ in frota}
    recusas = [f"o aparelho #{i} nao e' da frota do cliente #{cliente_id}"
               for i in sorted(set(ceder or ()) - conhecidos)]
    if recusas:
        return cliente, {}, recusas

    alvo = set(ceder) if ceder else quem_cede_por_padrao(frota)
    novos = renumerar_patrimonios(frota, alvo)
    atual = dict(frota)
    series = {ec.id: ec.serie for ec in db.query(EquipamentoCliente)
              .filter(EquipamentoCliente.id.in_(novos.keys())).all()} if novos else {}
    return cliente, {i: (series.get(i), atual[i], novo) for i, novo in novos.items()}, []


def aplicar(db, mudancas) -> int:
    for ec_id, (_serie, _de, para) in mudancas.items():
        db.execute(
            text("update equipamentos_cliente set patrimonio = :p where id = :i"),
            {"p": para, "i": ec_id},
        )
    return len(mudancas)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cliente", type=int, required=True, help="id do cliente")
    p.add_argument("--aparelhos", help="ids de equipamentos_cliente que cedem o numero")
    p.add_argument("--aplicar", action="store_true", help="grava de fato (sem isso, so simula)")
    args = p.parse_args()

    ceder = ({int(x) for x in args.aparelhos.split(",") if x.strip()}
             if args.aparelhos else None)

    db = SessionLocal()
    try:
        cliente, mudancas, recusas = planejar(db, args.cliente, ceder)
        if recusas:
            print("RECUSADO — nada foi gravado:")
            for r in recusas:
                print(f"     {r}")
            return
        if not mudancas:
            print(f'#{cliente.id} "{cliente.nome}": nenhum patrimonio repetido')
            return

        print(f'#{cliente.id} "{cliente.nome}"')
        for ec_id, (serie, de, para) in sorted(mudancas.items()):
            print(f"     aparelho #{ec_id} ({serie}): patrimonio {de} -> {para}")
        print()
        if not args.aplicar:
            print("(simulacao — rode com --aplicar para gravar)")
            return

        quantos = aplicar(db, mudancas)
        db.commit()
        print(f"gravado: {quantos} patrimonio(s) renumerado(s)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
