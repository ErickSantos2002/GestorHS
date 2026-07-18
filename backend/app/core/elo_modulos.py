"""Regras puras da carga do elo Phoebus<->Modulo (sem I/O, sem banco).

NAO confundir com `equipamentos_cliente.modulo`, uma coluna inteira legada sem
relacao com o modulo de calibracao do Phoebus.
"""
from datetime import datetime

_FORMATOS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d")


def parse_data(valor):
    if not valor:
        return None
    texto = str(valor).strip()
    for fmt in _FORMATOS:
        try:
            return datetime.strptime(texto, fmt)
        except ValueError:
            continue
    return None


def escolher_vencedor(linhas):
    """Entre linhas com a MESMA serie de modulo, vence a de maior 'Proxima Calibracao'.

    Um modulo so pode estar em um aparelho; a linha com calibracao mais recente e onde
    ele esta de fato (a outra e o aparelho onde ele estava). Sem data valida perde.
    Em empate exato de data, vence a primeira linha. Lista vazia devolve None.
    """
    if not linhas:
        return None
    melhor = linhas[0]
    melhor_data = parse_data(melhor.get("prox_calib"))
    for atual in linhas[1:]:
        data = parse_data(atual.get("prox_calib"))
        if data is not None and (melhor_data is None or data > melhor_data):
            melhor, melhor_data = atual, data
    return melhor


def resolver_elos(linhas, series_phoebus, series_modulo):
    """Aplica as 3 regras de carga. Devolve (elos, pendencias)."""
    elos, pendencias = [], []

    def pendencia(l, motivo):
        pendencias.append({
            "linha": l.get("linha"), "serie_aparelho": l.get("serie_aparelho"),
            "serie_modulo": l.get("serie_modulo"), "empresa": l.get("empresa"),
            "motivo": motivo,
        })

    # agrupa por serie de modulo para resolver duplicados
    por_modulo = {}
    for l in linhas:
        serie_mod = (l.get("serie_modulo") or "").strip()
        if not serie_mod:
            continue                      # aparelho sem modulo na planilha: ignora
        por_modulo.setdefault(serie_mod, []).append(l)

    for serie_mod, grupo in por_modulo.items():
        vencedora = escolher_vencedor(grupo) if len(grupo) > 1 else grupo[0]
        for l in grupo:
            if l is not vencedora:
                pendencia(l, "duplicado (modulo em outro aparelho mais recente)")
        serie_ap = (vencedora.get("serie_aparelho") or "").strip()
        phoebus_id = series_phoebus.get(serie_ap)
        modulo_id = series_modulo.get(serie_mod)
        if phoebus_id is None:
            pendencia(vencedora, "aparelho nao encontrado")
            continue
        if modulo_id is None:
            pendencia(vencedora, "modulo nao encontrado")
            continue
        elos.append({"linha": vencedora.get("linha"), "phoebus_id": phoebus_id, "modulo_id": modulo_id})

    elos.sort(key=lambda e: e["linha"])
    pendencias.sort(key=lambda p: p["linha"])
    return elos, pendencias
