"""Constantes e helpers do recebimento da OS (checklist de acessórios + condição)."""

# Lista fixa de acessórios do recebimento (id estável -> rótulo).
CHECKLIST_ACESSORIOS: dict[int, str] = {
    1: "Bobinas",
    2: "Bocal",
    3: "Cabos USB",
    4: "Capa",
    5: "Carregador veicular",
    6: "Carregadores AC/DC",
    7: "Impressora",
    8: "Maleta",
    9: "Nf de Remessa",
}

# Opções fixas do select "Condição de chegada".
CONDICOES_CHEGADA: tuple[str, ...] = (
    "Bom estado",
    "Com avarias",
    "Oxidado",
    "Lacrado",
    "Sem acessórios",
)


def checklist_ids_para_csv(ids: list[int] | None) -> str | None:
    """Valida ids contra a lista fixa, ordena, remove duplicados e junta em CSV.
    Retorna None se a lista for vazia/None. Levanta ValueError para id inválido."""
    if not ids:
        return None
    unicos = sorted(set(ids))
    for i in unicos:
        if i not in CHECKLIST_ACESSORIOS:
            raise ValueError(f"item de checklist inválido: {i}")
    return ",".join(str(i) for i in unicos)


def checklist_csv_para_ids(csv: str | None) -> list[int]:
    """Parse defensivo do CSV: ignora valores não-numéricos e ids fora da lista."""
    if not csv:
        return []
    ids: list[int] = []
    for parte in csv.split(","):
        parte = parte.strip()
        if parte.isdigit():
            n = int(parte)
            if n in CHECKLIST_ACESSORIOS:
                ids.append(n)
    return ids
