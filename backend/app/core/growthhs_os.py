"""Payload puro do card de OS liberada do laboratório, rumo ao GrowthHS.

Sem I/O: recebe a ordem, o cliente e o `device` já montado (quem consulta o
banco — inclusive a lógica de elo do Phoebus em `montar_device` — é o
chamador, fora deste módulo) e devolve o dict pronto para o cliente de
integração. Mesma convenção de `core/growthhs_payload.py` e
`core/growthhs_atrasados.py`.
"""
from datetime import date, timedelta

from app.core.growthhs_payload import montar_cliente, montar_contato

SOURCE_OS = "gestorhs.os"

# Limite do schema do GrowthHS (backend/app/schemas/integration.py):
# IntegrationCard.title = max_length 500.
LIMITE_TITLE = 500

DIAS_PRAZO = 2


def _texto(valor):
    """Normaliza para string não-vazia ou None (trata espaços em branco como vazio)."""
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None


def _fmt_data(valor):
    """Formata data/datetime em dd/mm/aaaa; None se ausente."""
    if valor is None:
        return None
    if hasattr(valor, "date"):
        valor = valor.date()
    return valor.strftime("%d/%m/%Y")


def _titulo(ordem, cliente) -> str:
    nome = _texto(getattr(cliente, "nome", None)) or ""
    equipamento = _texto(getattr(ordem, "equipamento_descricao", None)) or ""
    serie = _texto(getattr(ordem, "equipamento_serie", None)) or ""
    aparelho = " ".join(p for p in (equipamento, serie) if p)
    partes = [f"OS #{ordem.id}", nome, aparelho]
    titulo = " · ".join(p for p in partes if p)
    return titulo[:LIMITE_TITLE]


def _descricao(ordem) -> str:
    """Resultado do laboratório: situação, nº do certificado e próxima calibração.

    Omite as partes que não existirem — nunca deixa "None" vazar no texto.
    """
    situacao = _texto(getattr(ordem, "calib_situacao", None))
    cert = _texto(getattr(ordem, "calib_cert", None))
    prox = _fmt_data(getattr(ordem, "prox_calibragem", None))

    linhas = []
    if situacao:
        linhas.append(f"Resultado: {situacao}")
    if cert:
        linhas.append(f"Certificado: {cert}")
    if prox:
        linhas.append(f"Próxima calibração: {prox}")
    return " · ".join(linhas)


def montar_card_os(ordem, cliente, device: dict, board_id: int, hoje: date) -> dict:
    """Monta o corpo completo do POST em `/api/v1/integration/service-cards` para
    o card de UMA OS liberada do laboratório (um aparelho só, em `devices[]`).
    """
    return {
        "source": SOURCE_OS,
        "external_id": str(ordem.id),
        "board_id": board_id,
        "title": _titulo(ordem, cliente),
        "description": _descricao(ordem),
        # datetime COMPLETO, nao data pura: `due_date` e' `Optional[datetime]` no
        # schema do GrowthHS e o Pydantic v2 recusa "YYYY-MM-DD" com
        # "invalid datetime separator, expected `T`". Confirmado com 422 numa
        # chamada real em 18/07/2026 (ver core/growthhs_atrasados.py).
        "due_date": f"{(hoje + timedelta(days=DIAS_PRAZO)).isoformat()}T00:00:00",
        "client": montar_cliente(cliente),
        "contact": montar_contato(cliente),
        "devices": [device],
        "business_info": {
            "origem": "os liberada do laboratorio",
            "os_id": ordem.id,
            "tipo_servico": getattr(ordem, "tipo_servico", None),
        },
    }
