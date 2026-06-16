from datetime import date

from app.core.garantia import status_garantia, garantias


def test_sem_base_retorna_sem_registro():
    r = status_garantia(None, date(2026, 6, 16))
    assert r == {"estado": "sem_registro", "data_base": None, "vence_em": None}


def test_dentro_do_prazo_em_garantia():
    base = date(2026, 3, 12)
    r = status_garantia(base, date(2026, 6, 16))
    assert r["estado"] == "em_garantia"
    assert r["data_base"] == base
    assert r["vence_em"] == date(2027, 3, 12)


def test_fronteira_ultimo_dia_inclusive():
    base = date(2025, 6, 16)
    r = status_garantia(base, date(2026, 6, 16))
    assert r["estado"] == "em_garantia"


def test_dia_seguinte_ao_vencimento_fora():
    base = date(2025, 6, 16)
    r = status_garantia(base, date(2026, 6, 17))
    assert r["estado"] == "fora"
    assert r["vence_em"] == date(2026, 6, 16)


def test_bissexto_29_fev_vira_28_fev():
    base = date(2024, 2, 29)
    r = status_garantia(base, date(2024, 6, 1))
    assert r["vence_em"] == date(2025, 2, 28)


def test_garantias_resumo_qualquer_ativa():
    hoje = date(2026, 6, 16)
    r = garantias(
        datacompra=date(2020, 1, 1),
        ult_calibragem=date(2026, 1, 1),
        ult_manutencao=None,
        hoje=hoje,
    )
    assert r["em_garantia"] is True
    assert r["calibracao"]["estado"] == "em_garantia"
    assert r["manutencao"]["estado"] == "sem_registro"
    assert r["compra"]["estado"] == "fora"


def test_garantias_resumo_nenhuma_ativa():
    hoje = date(2026, 6, 16)
    r = garantias(date(2010, 1, 1), date(2010, 1, 1), None, hoje)
    assert r["em_garantia"] is False
