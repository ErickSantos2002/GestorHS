"""Payload puro do card de CAIXA liberada do laboratório, rumo ao GrowthHS.

Sem I/O: recebe a caixa, o cliente e os `devices` já montados (quem consulta o
banco — inclusive a lógica de elo do Phoebus em `montar_device` — é o
chamador, fora deste módulo) e devolve o dict pronto para o cliente de
integração. Mesma convenção de `core/growthhs_payload.py` e
`core/growthhs_atrasados.py`.

A unidade do card é a CAIXA, nunca a OS: um card por OS deixaria a mesma caixa
com dois cards no board. O construtor por OS foi removido em set/2026 junto com
o do TaskHS, pelo mesmo motivo.
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


def montar_card_caixa(caixa, cliente, devices: list[dict], board_id: int, hoje: date) -> dict:
    """Monta o corpo completo do POST em `/api/v1/integration/service-cards` para
    o card de uma CAIXA liberada do laboratório (múltiplos aparelhos em `devices[]`).
    """
    n = len(devices)
    titulo = " · ".join([f"CX {caixa.id}", _texto(getattr(cliente, "nome", None)) or "",
                         f"{n} aparelho" + ("s" if n != 1 else "")]).strip(" ·")
    return {
        "source": SOURCE_OS,
        "external_id": str(caixa.id),
        "board_id": board_id,
        "title": titulo[:LIMITE_TITLE],
        "description": f"{n} aparelho(s) liberado(s) do laboratório",
        "due_date": f"{(hoje + timedelta(days=DIAS_PRAZO)).isoformat()}T00:00:00",
        "client": montar_cliente(cliente),
        "contact": montar_contato(cliente),
        "devices": devices,
        "business_info": {"origem": "caixa liberada do laboratorio", "caixa_id": caixa.id},
    }
