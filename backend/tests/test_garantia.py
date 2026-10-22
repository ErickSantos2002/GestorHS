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


def test_manutencao_dura_3_meses():
    hoje = date(2026, 10, 22)
    r = garantias(None, None, date(2026, 6, 10), hoje)
    assert r["manutencao"]["vence_em"] == date(2026, 9, 10)
    assert r["manutencao"]["estado"] == "fora"
    assert r["em_garantia"] is False


def test_manutencao_dentro_dos_3_meses():
    r = garantias(None, None, date(2026, 8, 1), date(2026, 11, 1))
    assert r["manutencao"]["estado"] == "em_garantia"
    assert r["manutencao"]["vence_em"] == date(2026, 11, 1)


def test_manutencao_fim_de_mes_cai_no_ultimo_dia():
    r = garantias(None, None, date(2026, 11, 30), date(2026, 12, 1))
    assert r["manutencao"]["vence_em"] == date(2027, 2, 28)


def test_calibracao_e_compra_continuam_1_ano():
    hoje = date(2026, 10, 22)
    r = garantias(date(2026, 1, 15), date(2026, 2, 10), None, hoje)
    assert r["calibracao"]["vence_em"] == date(2027, 2, 10)
    assert r["compra"]["vence_em"] == date(2027, 1, 15)
