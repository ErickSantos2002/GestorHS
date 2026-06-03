"""Grafo de transições da Ordem de Serviço (linear). Puro, sem I/O."""

FASE_RECEBIDO = 4
FASE_FINALIZADA = 8
FASE_CANCELADA = 9

# fase atual -> próxima fase (linear)
PROXIMA = {4: 5, 5: 6, 6: 7, 7: 8}
ATIVAS = (4, 5, 6, 7)


def proxima_fase(fase: int) -> int | None:
    return PROXIMA.get(fase)


def eh_ativa(fase: int) -> bool:
    return fase in ATIVAS
