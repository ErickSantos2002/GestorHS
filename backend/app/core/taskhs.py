"""Integração GestorHS → TaskHS: lógica pura (sem I/O).

Monta o payload do card a partir de uma OS e mapeia fase → nome de lista.
As strings de lista são exatas (emoji incluso) — o TaskHS resolve por nome.
"""

SOURCE = "gestorhs"
BOARD = "Serviço"

FASE_PARA_LISTA: dict[int, str] = {
    4: "🚚 Expedição (Abrindo caixa)",
    5: "🔬Laboratório Calibração",
    6: "Serviços 🪛",
    7: "🚚 Expedição (Preparando para Envio)",
    8: "📮Correios",
}


def lista_da_fase(fase: int) -> str | None:
    return FASE_PARA_LISTA.get(fase)


def montar_titulo(ordem) -> str:
    partes = [f"OS #{ordem.id}"]
    if ordem.cliente_nome:
        partes.append(ordem.cliente_nome)
    descricao = ordem.equipamento_descricao or ordem.equipamento_serie
    if descricao:
        partes.append(descricao)
    return " · ".join(partes)


def montar_payload(ordem, *, lista: str, arquivado: bool) -> dict:
    due_date = ordem.prox_calibragem.date().isoformat() if ordem.prox_calibragem else None
    return {
        "source": SOURCE,
        "external_id": str(ordem.id),
        "board": BOARD,
        "list": lista,
        "title": montar_titulo(ordem),
        "description": ordem.obs or None,
        "due_date": due_date,
        "priority": "medium",
        "archived": arquivado,
    }
