"""Classificacao pura dos eventos de integracao (sem I/O)."""

# source do payload -> tipo, por integracao
_TIPOS_GROWTHHS = {
    "gestorhs.os": "os_card",
    "gestorhs.atrasados": "atrasados",
    "gestorhs.calibracao": "vencendo",
}


def classificar_tipo(integracao: str, source: str | None) -> str:
    if integracao == "taskhs":
        return "os_espelho"
    if integracao == "growthhs" and source:
        return _TIPOS_GROWTHHS.get(source, "desconhecido")
    return "desconhecido"


def referencia_os_do_payload(tipo: str, payload: dict | None) -> int | None:
    """Para eventos de OS, a referencia e o proprio external_id (id da OS).
    Vencendo/atrasados nao referenciam OS."""
    if payload is None or tipo not in ("os_card", "os_espelho"):
        return None
    try:
        return int(payload.get("external_id"))
    except (TypeError, ValueError):
        return None
