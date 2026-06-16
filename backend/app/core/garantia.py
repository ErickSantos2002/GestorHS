"""Calculo das garantias do aparelho (calibracao, manutencao, compra).

Puro, sem I/O. Cada garantia dura 1 ano a partir da sua data base.
"""
from datetime import date

DURACAO_GARANTIA_ANOS = 1


def _mais_um_ano(base: date) -> date:
    """base + 1 ano (mesma data no ano seguinte); 29/fev -> 28/fev."""
    try:
        return base.replace(year=base.year + DURACAO_GARANTIA_ANOS)
    except ValueError:
        # 29/fev em ano de destino nao bissexto
        return base.replace(year=base.year + DURACAO_GARANTIA_ANOS, day=28)


def status_garantia(base: date | None, hoje: date) -> dict:
    """Status de uma garantia a partir da data base.

    sem base -> sem_registro
    com base -> em_garantia enquanto hoje <= vence_em (inclusive), senao fora.
    """
    if base is None:
        return {"estado": "sem_registro", "data_base": None, "vence_em": None}
    vence_em = _mais_um_ano(base)
    estado = "em_garantia" if hoje <= vence_em else "fora"
    return {"estado": estado, "data_base": base, "vence_em": vence_em}


def garantias(
    datacompra: date | None,
    ult_calibragem: date | None,
    ult_manutencao: date | None,
    hoje: date,
) -> dict:
    """Monta os 3 status + resumo (em_garantia = qualquer uma ativa)."""
    calibracao = status_garantia(ult_calibragem, hoje)
    manutencao = status_garantia(ult_manutencao, hoje)
    compra = status_garantia(datacompra, hoje)
    em_garantia = any(
        g["estado"] == "em_garantia" for g in (calibracao, manutencao, compra)
    )
    return {
        "em_garantia": em_garantia,
        "calibracao": calibracao,
        "manutencao": manutencao,
        "compra": compra,
    }
