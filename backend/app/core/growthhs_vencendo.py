"""Montagem do card de calibração VENCENDO (janela dos 50 dias) do GrowthHS.

Sem I/O: recebe uma linha já lida do banco e devolve o dict pronto para o cliente
de integração — mesma convenção de `core/growthhs_payload.py` e
`core/growthhs_atrasados.py`.

Diferença deliberada para a Etapa 1 (atrasados): lá o card é POR CLIENTE, aqui é
POR APARELHO. A Etapa 1 é um retrato único, tirado uma vez; agrupar por cliente é
seguro. Esta etapa tem janela ROLANTE — se a chave fosse por cliente, o segundo
aparelho a entrar na janela depois do card já existir devolveria o card antigo
(`created: false`) e nunca apareceria, sem erro nenhum.
"""
from datetime import date

from app.core.growthhs_payload import montar_cliente, montar_contato, montar_device

SOURCE_VENCENDO = "gestorhs.calibracao"


def montar_card_vencendo(linha: dict, hoje: date, board_id: int) -> dict:
    """Monta o corpo do POST em `/api/v1/integration/service-cards` para UM aparelho
    com calibração a vencer.

    `linha` é `{cliente_id, cliente, ec, equipamento_desc, elo}` — o mesmo formato da
    Etapa 1, para que ambos os scripts compartilhem `buscar_elo`.
    """
    cliente = linha["cliente"]
    ec = linha["ec"]
    equipamento_desc = linha["equipamento_desc"] or ""
    prox = ec.prox_calibragem
    nome = getattr(cliente, "nome", None) or ""
    serie = getattr(ec, "serie", None) or ""
    dias = (prox - hoje).days

    return {
        "source": SOURCE_VENCENDO,
        # A chave NAO leva a data da execucao — e' o que torna o job diario
        # idempotente: rodar de novo devolve `created: false` e nao duplica.
        "external_id": f"{ec.id}:{prox:%Y-%m-%d}",
        "board_id": board_id,
        "title": f"Calibração vencendo · {nome} · {equipamento_desc} {serie}".rstrip(),
        "description": (
            f"Calibração vence em {dias} dia(s), em {prox.strftime('%d/%m/%Y')} — "
            f"{equipamento_desc} série {serie}"
        ),
        # datetime COMPLETO: `due_date` e' `Optional[datetime]` no schema do GrowthHS
        # e o Pydantic v2 recusa "YYYY-MM-DD". Confirmado com 422 real em 18/07/2026.
        "due_date": f"{prox.isoformat()}T00:00:00",
        "client": montar_cliente(cliente),
        "contact": montar_contato(cliente),
        "devices": [montar_device(ec, equipamento_desc, elo=linha.get("elo"))],
        "business_info": {
            "origem": "calibracao vencendo",
            "cliente_id": linha["cliente_id"],
            "equipamento_cliente_id": ec.id,
            "dias_para_vencer": dias,
        },
    }
