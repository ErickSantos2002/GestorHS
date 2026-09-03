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
    """Para eventos de card, a referencia e o proprio external_id. Desde set/2026 esse
    id e' de CAIXA (ver `referencia_e_de_caixa`); linha antiga pode ser de OS.
    Vencendo/atrasados nao referenciam nada."""
    if payload is None or tipo not in ("os_card", "os_espelho"):
        return None
    try:
        return int(payload.get("external_id"))
    except (TypeError, ValueError):
        return None


def referencia_e_de_caixa(payload: dict | None) -> bool:
    """O numero da referencia aponta para uma CAIXA, e nao para uma OS.

    Desde set/2026 todo card das integracoes e' de caixa, entao o `external_id` de
    payload de card e' id de caixa. As linhas antigas, de quando existia card por OS,
    se distinguem pelo TITULO: so o card por OS levava "OS #" nele. Linha sem payload
    nao e' card — e' um pulo registrado com o id da OS na mao (`referencia_os=`), que
    continua apontando para a OS.

    So afirma "caixa" com titulo na mao: sem ele nao da pra distinguir, e cair no
    default antigo (OS) mantem a tela como sempre foi para linha malformada.
    """
    titulo = (payload or {}).get("title")
    if not titulo:
        return False
    return "OS #" not in titulo
