"""Composicao dos textos do Relatorio de Manutencao.

Puro, sem I/O. Duas saidas alimentam o documento:
- "Tipo do Problema": os servicos escolhidos, em lista portuguesa;
- "Resumo do Servico": as frases padrao desses servicos, emendadas.

O resultado e' GRAVADO na manutencao, nunca recomposto na hora de imprimir —
senao editar o catalogo amanha reescreveria relatorio ja emitido, e relatorio
emitido e' documento.
"""


def _limpar(itens: list[str]) -> list[str]:
    return [i.strip() for i in itens if i and i.strip()]


def _sem_ponto_final(texto: str) -> str:
    return texto[:-1] if texto.endswith(".") else texto


def compor_problema(descricoes: list[str]) -> str:
    """Lista portuguesa dos servicos, terminada em ponto.

    Um -> "A."   Dois -> "A e B."   Tres ou mais -> "A, B e C."
    """
    itens = [_sem_ponto_final(d) for d in _limpar(descricoes)]
    if not itens:
        return ""
    if len(itens) == 1:
        corpo = itens[0]
    else:
        corpo = f"{', '.join(itens[:-1])} e {itens[-1]}"
    return f"{corpo}."


def compor_resumo(frases: list[str]) -> str:
    """Emenda as frases padrao, garantindo ponto final entre elas."""
    itens = _limpar(frases)
    if not itens:
        return ""
    return " ".join(f"{_sem_ponto_final(f)}." for f in itens)
