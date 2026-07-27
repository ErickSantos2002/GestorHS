"""Montagem do card de calibração VENCENDO do GrowthHS — um card por CLIENTE por mês.

Sem I/O: recebe linhas já lidas do banco e devolve o dict pronto para o cliente de
integração — mesma convenção de `core/growthhs_payload.py` e `core/growthhs_atrasados.py`.

Por que por cliente e não por aparelho: o comercial cobra todos os aparelhos do
cliente na primeira ligação; um card por aparelho obrigava a repetir o mesmo
fechamento em N cards. O agrupamento só é seguro porque a varredura virou MENSAL —
com a janela rolante diária de antes, o segundo aparelho a entrar na janela depois do
card já existir devolveria `created: false` e sumiria sem erro nenhum.
"""
from datetime import date

from app.core.growthhs_payload import montar_cliente, montar_contato, montar_device

SOURCE_VENCENDO = "gestorhs.calibracao"

# `business_info.acquisition_channel` — o board de Cobranca do GrowthHS exibe isso como
# "Canal de aquisicao". O servico de integracao de la NAO preenche o campo (so deriva
# `collection_type` a partir do `source`), entao quem manda e' o GestorHS.
#
# A string precisa bater EXATAMENTE com a opcao do select em
# `ServiceCardDetails.tsx` — repare no S minusculo de "GestorHs". Qualquer diferenca
# grava um valor fora da lista e o dropdown fica mostrando lixo.
CANAL_AQUISICAO = "Importação (GestorHs)"

# Nome do mês em PT-BR sem depender de `locale`, que varia com o que está instalado
# na imagem — em produção a imagem sobe pelo Dockerfile, onde não há garantia de
# locale pt_BR gerado.
MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho",
         "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")


def _competencia_extenso(competencia: date) -> str:
    return f"{MESES[competencia.month - 1]}/{competencia.year}"


def _linha_descricao(linha: dict) -> str:
    """Uma linha da lista de aparelhos do card.

    Com elo, mostra o Phoebus e o módulo entre parênteses — mesmo critério do
    `montar_device`, pelo mesmo motivo: o cliente reconhece o aparelho, não o número
    do módulo.
    """
    ec = linha["ec"]
    elo = linha.get("elo")
    if elo is not None:
        descricao, serie, modulo = elo.descricao, elo.serie, ec.serie
    else:
        descricao, serie, modulo = linha["equipamento_desc"], ec.serie, None

    texto = (descricao or "").strip() or "Aparelho"
    if serie:
        texto += f" série {serie}"
    if modulo:
        texto += f" (módulo {modulo})"
    return f"- {texto} — vence {ec.prox_calibragem.strftime('%d/%m/%Y')}"


def montar_card_vencendo(linhas: list[dict], competencia: date, board_id: int) -> dict:
    """Monta o corpo do POST em `/api/v1/integration/service-cards` para TODOS os
    aparelhos de UM cliente que vencem na competência.

    `linhas` são dicts `{cliente_id, cliente, ec, equipamento_desc, elo}` de um mesmo
    cliente — o formato que `buscar_vencendo` devolve. `competencia` é um `date` no
    dia 1 do mês.
    """
    linhas = sorted(linhas, key=lambda l: (l["ec"].prox_calibragem, l["ec"].id))
    primeira = linhas[0]
    cliente = primeira["cliente"]
    cliente_id = primeira["cliente_id"]
    nome = getattr(cliente, "nome", None) or ""
    quantos = len(linhas)
    palavra = "aparelho" if quantos == 1 else "aparelhos"
    mes = _competencia_extenso(competencia)
    lista = "\n".join(_linha_descricao(linha) for linha in linhas)

    return {
        "source": SOURCE_VENCENDO,
        # A chave nao leva a data da execucao NEM o aparelho: e' o que torna a rodada
        # mensal idempotente. Como toda rodada varre mes corrente + seguinte, o mes de
        # tras ja tem card e volta `created: false`.
        "external_id": f"{cliente_id}:{competencia:%Y-%m}",
        "board_id": board_id,
        "title": f"Calibração vencendo · {nome} · {quantos} {palavra} · {mes}",
        "description": (
            f"{quantos} {palavra} deste cliente com calibração vencendo em {mes}:"
            f"\n\n{lista}"
        ),
        # O prazo do card e' o do aparelho MAIS URGENTE do grupo — quando a cobranca
        # precisa ter acontecido. datetime COMPLETO: `due_date` e' `Optional[datetime]`
        # no schema do GrowthHS e o Pydantic v2 recusa "YYYY-MM-DD" (422 real em 18/07/2026).
        "due_date": f"{linhas[0]['ec'].prox_calibragem.isoformat()}T00:00:00",
        "client": montar_cliente(cliente),
        "contact": montar_contato(cliente),
        "devices": [
            montar_device(l["ec"], l["equipamento_desc"], elo=l.get("elo")) for l in linhas
        ],
        "business_info": {
            "origem": "calibracao vencendo",
            "acquisition_channel": CANAL_AQUISICAO,
            "cliente_id": cliente_id,
            "competencia": f"{competencia:%Y-%m}",
            "qtd_aparelhos": quantos,
            "equipamento_cliente_ids": [l["ec"].id for l in linhas],
        },
    }
