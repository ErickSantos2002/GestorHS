"""Workflow puro de status da caixa: Pendente (P) → Aberta (A) → Finalizada (F)."""

PENDENTE = "P"
ABERTA = "A"
FINALIZADA = "F"

# transições lineares válidas (status atual → próximo permitido)
TRANSICOES = {PENDENTE: ABERTA, ABERTA: FINALIZADA}


def pode_vincular(status: str) -> bool:
    """Só dá para vincular/abrir OS enquanto a caixa não está Finalizada."""
    return status in (PENDENTE, ABERTA)


def proximo_status(atual: str) -> str | None:
    return TRANSICOES.get(atual)


def validar_transicao(atual: str, novo: str) -> None:
    """Levanta ValueError se a transição não for a próxima permitida."""
    if TRANSICOES.get(atual) != novo:
        raise ValueError(f"transição inválida: {atual} → {novo}")
