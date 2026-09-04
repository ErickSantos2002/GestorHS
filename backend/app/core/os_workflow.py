"""Grafo de transições da Ordem de Serviço (linear). Puro, sem I/O."""

FASE_RECEBIDO = 4
FASE_LABORATORIO = 5
FASE_FINANCEIRO = 10
FASE_PREPARANDO = 7
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


DESFECHO_PENDENTE = "pendente"
DESFECHO_CONCLUIDO = "concluido"
DESFECHO_SEM_CONSERTO = "sem_conserto"
DESFECHO_LIBERADO = "liberado"
DESFECHOS_TERMINAIS = (DESFECHO_CONCLUIDO, DESFECHO_SEM_CONSERTO, DESFECHO_LIBERADO)


def desfechos_pendentes(desfechos: list[str]) -> int:
    """Quantos aparelhos ainda estao 'pendente' no laboratorio."""
    return sum(1 for d in desfechos if d not in DESFECHOS_TERMINAIS)


def pode_avancar_caixa(fase_atual: int, desfechos: list[str]) -> tuple[bool, str | None]:
    """Regras de avanco da CAIXA. So a saida do laboratorio checa desfecho por aparelho.

    Retorna (True, None) se pode avancar; (False, motivo) se travado.
    """
    if proxima_fase(fase_atual) is None:
        return False, "caixa em fase terminal"
    if fase_atual == FASE_LABORATORIO:
        faltam = desfechos_pendentes(desfechos)
        if faltam > 0:
            return False, f"faltam {faltam} aparelho(s) sem desfecho no laboratorio"
    return True, None
