"""Regra de "esta caixa pode apontar para esta proposta?" (sem I/O).

O numero da proposta da caixa vem digitado a mao no card do GrowthHS e o inbound do
Ganho grava sem conferir. Esta e' a conferencia que faltou: so aceita proposta do
MESMO cliente da caixa. Dois chamadores: `PUT /caixas/{id}/proposta` (a tela) e o
script `corrigir_proposta_caixa`.
"""


def clientes_da_caixa(caixa) -> set[int]:
    """Clientes que a caixa representa: o principal mais os de todas as OS.

    As canceladas entram de proposito — elas mantem o vinculo com a caixa, e a
    proposta pode ter sido montada antes do cancelamento.
    """
    ids = {o.cliente for o in caixa.ordens if o.cliente is not None}
    if caixa.cliente_principal is not None:
        ids.add(caixa.cliente_principal)
    return ids


def conferir(caixa, proposta) -> str | None:
    """Motivo da recusa, ou None se a caixa pode apontar para essa proposta."""
    if proposta.is_deleted:
        return f"proposta {proposta.numero} esta desabilitada"
    if proposta.cliente is None:
        return f"proposta {proposta.numero} esta sem cliente"
    donos = clientes_da_caixa(caixa)
    if not donos:
        return f"caixa {caixa.id} nao tem cliente nenhum — nao da para conferir"
    if proposta.cliente not in donos:
        return (f"proposta {proposta.numero} e' do cliente {proposta.cliente}, "
                f"que nao e' da caixa {caixa.id} (clientes da caixa: "
                f"{sorted(donos)}) — e' o mesmo erro que se quer corrigir")
    return None
