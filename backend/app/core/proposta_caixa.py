"""Regra de "esta caixa pode apontar para esta proposta?" (sem I/O).

O numero da proposta da caixa vem digitado a mao no card do GrowthHS e o inbound do
Ganho grava sem conferir. Esta e' a conferencia que faltou: so aceita proposta do
MESMO cliente da caixa. Chamadores: `aplicar_troca_proposta` em `api/caixas.py` (a tela
e o inbound do GrowthHS) e o script `corrigir_proposta_caixa`.
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


def _nome_cliente(cliente_id: int, rel) -> str:
    return rel.nome if rel is not None and rel.nome else f"cliente {cliente_id}"


def nomes_da_caixa(caixa) -> list[str]:
    """Nomes dos clientes de `clientes_da_caixa`, para a mensagem de recusa."""
    nomes = {}
    for o in caixa.ordens:
        if o.cliente is not None:
            nomes[o.cliente] = _nome_cliente(o.cliente, getattr(o, "cliente_rel", None))
    if caixa.cliente_principal is not None:
        nomes[caixa.cliente_principal] = _nome_cliente(
            caixa.cliente_principal, getattr(caixa, "cliente_principal_rel", None))
    return sorted(nomes.values())


def conferir(caixa, proposta) -> str | None:
    """Motivo da recusa, ou None se a caixa pode apontar para essa proposta.

    O texto vai direto para o usuario final (toast do GrowthHS), entao cita os
    clientes pelo nome, nao pelo id."""
    if proposta.is_deleted:
        return f"a proposta #{proposta.numero} está desabilitada"
    if proposta.cliente is None:
        return f"a proposta #{proposta.numero} está sem cliente"
    donos = clientes_da_caixa(caixa)
    if not donos:
        return f"a caixa #{caixa.id} não tem cliente — não dá para conferir a proposta"
    if proposta.cliente not in donos:
        dono = _nome_cliente(proposta.cliente, getattr(proposta, "cliente_rel", None))
        return (f"a proposta #{proposta.numero} é do cliente {dono}, que não está na "
                f"caixa #{caixa.id} (clientes da caixa: {', '.join(nomes_da_caixa(caixa))})")
    return None
