"""Calculo das garantias do aparelho (calibracao, manutencao, compra).

Puro, sem I/O. Calibracao e compra duram 1 ano a partir da sua data base;
manutencao dura 3 meses.
"""
import calendar
from datetime import date

DURACAO_GARANTIA_MESES = 12
DURACAO_GARANTIA_MANUTENCAO_MESES = 3


def _somar_meses(base: date, meses: int) -> date:
    """base + N meses; dia que nao existe no mes de destino vira o ultimo dia
    (31/jan + 1 mes -> 28/fev; 29/fev + 12 meses -> 28/fev)."""
    total = base.month - 1 + meses
    ano, mes = base.year + total // 12, total % 12 + 1
    dia = min(base.day, calendar.monthrange(ano, mes)[1])
    return date(ano, mes, dia)


def status_garantia(
    base: date | None, hoje: date, meses: int = DURACAO_GARANTIA_MESES
) -> dict:
    """Status de uma garantia a partir da data base.

    sem base -> sem_registro
    com base -> em_garantia enquanto hoje <= vence_em (inclusive), senao fora.
    """
    if base is None:
        return {"estado": "sem_registro", "data_base": None, "vence_em": None}
    vence_em = _somar_meses(base, meses)
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
    manutencao = status_garantia(
        ult_manutencao, hoje, DURACAO_GARANTIA_MANUTENCAO_MESES
    )
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
