"""Regras puras da unificacao de cadastros duplicados de cliente.

Duplicado aqui e' o mesmo CNPJ cadastrado duas vezes — nao a matriz e a filial,
que sao CNPJs diferentes e clientes diferentes de verdade. O par 1059/1064
(FERTILIZANTES TOCANTINS, 05571228001127) era byte-a-byte identico nos dois
cadastros; a frota e' que estava dividida em cinco aparelhos de cada lado.

Sem I/O: quem le e grava e' `app.scripts.unificar_clientes`.
"""

# Campos do cadastro que precisam bater para o par ser considerado o mesmo
# cliente. Fora da lista, de proposito:
#   id     — diferem sempre, e' o que estamos unificando
#   ativo  — o absorvido vai deixar de existir; o flag dele nao decide nada
#   datcad — data de cadastro; o duplicado nasceu depois por definicao
CAMPOS_COMPARADOS = (
    "grupo", "nome", "cgc", "cpf", "endereco", "numero", "complemento", "bairro",
    "municipio", "estado", "cep", "contato", "email", "telefones", "celular",
    "whatsapp", "whatsapp1", "whatsapp2", "insc_mun", "insc_est", "obs", "imagem",
)


def _normalizar(valor):
    """String vazia, so espacos e NULL sao a mesma ausencia de dado.

    O cadastro antigo tem `whatsapp` ora como '' ora como NULL na mesma dupla —
    tratar isso como divergencia recusaria pares que ninguem chamaria de
    diferentes.
    """
    if valor is None:
        return None
    if isinstance(valor, str):
        return valor.strip() or None
    return valor


def divergencias(fica, vai) -> list[tuple[str, object, object]]:
    """Campos em que os dois cadastros discordam, como (campo, do_que_fica, do_que_vai).

    Lista vazia = os dois sao o mesmo cliente escrito duas vezes, e unificar nao
    perde informacao nenhuma.
    """
    saida = []
    for campo in CAMPOS_COMPARADOS:
        a = _normalizar(getattr(fica, campo, None))
        b = _normalizar(getattr(vai, campo, None))
        if a != b:
            saida.append((campo, a, b))
    return saida


def escolher_sobrevivente(pesos: list[dict]) -> int:
    """Qual dos cadastros fica, dado [{'id':…, 'caixas':…, 'ordens':…}, …].

    Caixa pesa mais que OS porque caixa viva e' um card ja publicado no TaskHS e
    no GrowthHS pelo id do cliente: mover o cliente principal de uma caixa em
    andamento troca o dado embaixo de um card que a expedicao esta olhando
    agora. OS antiga e' historico, ninguem esta com ela na mao.
    """
    return min(pesos, key=lambda p: (-p["caixas"], -p["ordens"], p["id"]))["id"]


def renumerar_patrimonios(frota, ceder) -> dict[int, str]:
    """Resolve patrimonio repetido dentro da frota de UM cliente.

    `frota` e' [(id_do_equipamento_cliente, patrimonio)] do cliente inteiro;
    `ceder` sao os ids que abrem mao do numero quando ele ja e' de outro —
    depois de unificar, os que vieram do cadastro absorvido. Devolve so quem
    muda, como {id: patrimonio_novo}.

    `patrimonio` e' etiqueta do cliente e sai no certificado pelo token
    `[patrimonio]`, entao mexe-se no minimo: quem nao cede nunca anda, e quem
    cede sem colidir tambem fica parado.

    A numeracao nova continua do MAIOR ocupado, nao preenche buraco: reusar um
    numero aposentado confundiria quem conhece a etiqueta antiga.

    Valor nao numerico fica intocado — em 203 aparelhos o campo virou recado
    ("SEM CONSERTO", uma data), e renumerar isso apagaria a informacao.
    """
    numericos = {i: p.strip() for i, p in frota
                 if isinstance(p, str) and p.strip().isdigit()}
    ocupados = {int(p) for i, p in numericos.items() if i not in ceder}
    proximo = max(ocupados, default=0) + 1

    saida = {}
    for i, p in sorted(numericos.items()):
        if i not in ceder or int(p) not in ocupados:
            continue
        saida[i] = str(proximo)
        ocupados.add(proximo)
        proximo += 1
    return saida
