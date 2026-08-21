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


# ── Proxima calibracao ───────────────────────────────────────────────────────
# A calibracao vale 1 ano. Ate o go-live quem calculava era o sistema antigo; o
# GestorHS herdou a coluna mas nunca a preenchia, e o aparelho recem-calibrado
# seguia com a data do ciclo anterior — virando "Vencido" sozinho.

from app.core.calibracao import proxima_calibracao


def test_proxima_calibracao_e_um_ano_depois():
    assert proxima_calibracao(date(2026, 7, 30)) == date(2027, 7, 30)


def test_proxima_calibracao_sem_data_nao_inventa():
    assert proxima_calibracao(None) is None


def test_proxima_calibracao_em_29_de_fevereiro_cai_no_dia_28():
    """2028 e bissexto, 2029 nao — sem tratar, o replace(year=...) levantaria."""
    assert proxima_calibracao(date(2028, 2, 29)) == date(2029, 2, 28)
