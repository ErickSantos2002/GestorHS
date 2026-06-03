from datetime import date, timedelta
from app.core.calibracao import status_calibracao

HOJE = date(2026, 6, 1)


def test_sem_data():
    assert status_calibracao(None, HOJE) == "sem_data"


def test_vencido():
    assert status_calibracao(HOJE - timedelta(days=1), HOJE) == "vencido"


def test_vencendo_no_proprio_dia():
    assert status_calibracao(HOJE, HOJE) == "vencendo"


def test_vencendo_na_borda_90():
    assert status_calibracao(HOJE + timedelta(days=90), HOJE) == "vencendo"


def test_em_dia_apos_90():
    assert status_calibracao(HOJE + timedelta(days=91), HOJE) == "em_dia"
