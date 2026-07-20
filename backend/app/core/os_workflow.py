"""Grafo de transições da Ordem de Serviço (linear). Puro, sem I/O."""

FASE_RECEBIDO = 4
FASE_LABORATORIO = 5
FASE_FINANCEIRO = 10
FASE_FINALIZADA = 8
FASE_CANCELADA = 9

# fase atual -> próxima fase (linear). Financeiro(10) entra entre Pós-Vendas(6) e Preparando Retorno(7).
PROXIMA = {4: 5, 5: 6, 6: 10, 10: 7, 7: 8}
ATIVAS = (4, 5, 6, 10, 7)

# Ordem lógica das fases (o ID 10 é numericamente maior que 7/8; use isto, não o ID cru).
ORDEM_FASES = {4: 0, 5: 1, 6: 2, 10: 3, 7: 4, 8: 5}


def proxima_fase(fase: int) -> int | None:
    return PROXIMA.get(fase)


def eh_ativa(fase: int) -> bool:
    return fase in ATIVAS


def posicao(fase: int) -> int:
    """Posição lógica da fase na sequência (fora do mapa -> fim)."""
    return ORDEM_FASES.get(fase, 99)
