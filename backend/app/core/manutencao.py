"""Composicao dos textos do Relatorio de Manutencao.

Puro, sem I/O. Duas saidas alimentam o documento:
- "Tipo do Problema": os servicos escolhidos, em lista portuguesa;
- "Resumo do Servico": as frases padrao desses servicos, emendadas.

O Resumo do Servico e' GRAVADO na manutencao e fica congelado dali em diante —
e' prosa editada a mao, e editar o catalogo amanha nao pode reescrever um
resumo que alguem ja revisou.

Ja a linha do Tipo do Problema NAO e' gravada: ela deriva dos servicos ligados
a manutencao e e' recomposta a cada geracao do certificado, do mesmo jeito que
o certificado ja rederiva dados de cliente e aparelho toda vez que e' regerado.
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


def _descrever_aparelho(modelo: str | None, serie: str | None) -> str:
    """Modelo e serie do aparelho, aguentando cadastro incompleto.

    Sem tratamento, um aparelho sem serie produziria "equipamento Mercury / nº de
    série ," — frase quebrada num documento que vai para o cliente.
    """
    partes = [p for p in (
        (modelo or "").strip(),
        f"nº de série {serie.strip()}" if (serie or "").strip() else "",
    ) if p]
    return " / ".join(partes) if partes else "não identificado"


def compor_resumo(modelo: str | None, serie: str | None,
                  servicos: list[tuple[str | None, str]]) -> str:
    """Texto padrao do "Resumo do Servico".

    O aparelho e a frase de conformidade aparecem UMA vez; so os servicos se
    repetem. Emendar uma frase completa por servico repetia os dois a cada item
    e, com tres ou mais, o resumo ficava longo e confuso.
    """
    itens = [(codigo, descricao.strip()) for codigo, descricao in servicos if descricao and descricao.strip()]
    if not itens:
        return ""
    lista = "; ".join(
        f"{codigo.strip()} – {descricao}" if (codigo or "").strip() else descricao
        for codigo, descricao in itens
    )
    rotulo = "referente ao serviço" if len(itens) == 1 else "referente aos serviços"
    return (
        f"Foi realizada a manutenção no equipamento {_descrever_aparelho(modelo, serie)}, "
        f"em conformidade com os procedimentos técnicos da Health & Safety, "
        f"{rotulo}: {lista}."
    )
