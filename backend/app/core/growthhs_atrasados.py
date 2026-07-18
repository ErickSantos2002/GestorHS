"""Agrupamento por cliente e montagem do card de atrasados do GrowthHS.

Sem I/O: recebe as linhas já lidas do banco (uma por equipamento vencido) e devolve
dicts prontos para o cliente de integração. Quem consulta o banco é o chamador (o
script da Etapa 1, fora deste módulo) — mesma convenção de `core/growthhs_payload.py`.
"""
from datetime import date

from app.core.growthhs_payload import montar_cliente, montar_contato, montar_device

SOURCE_ATRASADOS = "gestorhs.atrasados"


def agrupar_por_cliente(linhas: list[dict]) -> list[dict]:
    """Agrupa linhas `{cliente_id, cliente, ec, equipamento_desc, elo}` por cliente.

    Devolve, por cliente, `{cliente_id, cliente, itens, vencimento_mais_antigo}` —
    `itens` são as próprias linhas daquele cliente. Ordenação determinística:
    clientes por `cliente_id` crescente e, dentro de cada um, itens pela
    `prox_calibragem` mais antiga primeiro.
    """
    por_cliente: dict[int, dict] = {}
    for linha in linhas:
        cliente_id = linha["cliente_id"]
        grupo = por_cliente.get(cliente_id)
        if grupo is None:
            grupo = {"cliente_id": cliente_id, "cliente": linha["cliente"], "itens": []}
            por_cliente[cliente_id] = grupo
        grupo["itens"].append(linha)

    grupos = []
    for cliente_id in sorted(por_cliente):
        grupo = por_cliente[cliente_id]
        grupo["itens"].sort(key=lambda item: (item["ec"].prox_calibragem, item["ec"].id))
        grupo["vencimento_mais_antigo"] = grupo["itens"][0]["ec"].prox_calibragem
        grupos.append(grupo)

    return grupos


def _plural(qtd: int, singular: str, plural: str) -> str:
    return singular if qtd == 1 else plural


def montar_card_atrasados(grupo: dict, data_carga: date, board_id: int) -> dict:
    """Monta o corpo completo do POST em `/api/v1/integration/service-cards` para
    o card de atrasados de UM cliente (todos os aparelhos vencidos dele em `devices[]`).
    """
    cliente = grupo["cliente"]
    itens = grupo["itens"]
    qtd = len(itens)
    vencimento_mais_antigo = grupo["vencimento_mais_antigo"]
    nome = getattr(cliente, "nome", None) or ""

    devices = [
        montar_device(item["ec"], item["equipamento_desc"], elo=item.get("elo"))
        for item in itens
    ]

    aparelho = _plural(qtd, "aparelho", "aparelhos")
    title = f"Calibração vencida · {nome} · {qtd} {aparelho}"
    description = (
        f"{qtd} {aparelho} com calibração vencida — vencimento mais antigo em "
        f"{vencimento_mais_antigo.strftime('%d/%m/%Y')}"
    )

    return {
        "source": SOURCE_ATRASADOS,
        "external_id": f"{grupo['cliente_id']}:{data_carga:%Y-%m-%d}",
        "board_id": board_id,
        "title": title,
        "description": description,
        # datetime COMPLETO, nao data pura: `due_date` e' `Optional[datetime]` no
        # schema do GrowthHS e o Pydantic v2 recusa "YYYY-MM-DD" com
        # "invalid datetime separator, expected `T`". Confirmado com 422 numa
        # chamada real em 18/07/2026 — o contrato (§3) diz que aceita data pura,
        # mas nao aceita; os exemplos de curl do proprio documento falhariam.
        "due_date": f"{vencimento_mais_antigo.isoformat()}T00:00:00",
        "client": montar_cliente(cliente),
        "contact": montar_contato(cliente),
        "devices": devices,
        "business_info": {
            "origem": "backfill atrasados",
            "cliente_id": grupo["cliente_id"],
            "qtd_equipamentos": qtd,
        },
    }
