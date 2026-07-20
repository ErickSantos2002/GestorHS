from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.agendamento import TZ_SP, proxima_execucao, segundos_ate_proxima

UTC = ZoneInfo("UTC")


def _sp(ano, mes, dia, hora, minuto=0):
    return datetime(ano, mes, dia, hora, minuto, tzinfo=TZ_SP)


def test_hoje_mais_tarde_agenda_para_hoje():
    agora = _sp(2026, 7, 20, 6, 30)
    assert proxima_execucao(agora, 8) == _sp(2026, 7, 20, 8)


def test_ja_passou_agenda_para_amanha():
    agora = _sp(2026, 7, 20, 9, 15)
    assert proxima_execucao(agora, 8) == _sp(2026, 7, 21, 8)


def test_exatamente_no_horario_agenda_para_amanha():
    """Nao disparar imediatamente ao subir exatamente as 08:00 — senao um restart
    as 08:00:00 rodaria o job de novo no mesmo instante."""
    agora = _sp(2026, 7, 20, 8, 0)
    assert proxima_execucao(agora, 8) == _sp(2026, 7, 21, 8)


def test_vira_o_mes():
    agora = _sp(2026, 7, 31, 23, 50)
    assert proxima_execucao(agora, 8) == _sp(2026, 8, 1, 8)


def test_horario_e_o_de_sao_paulo_nao_utc():
    """O container roda em UTC. As 23:00 UTC ja e' o dia seguinte em SP? Nao —
    SP e' UTC-3, entao 23:00 UTC = 20:00 em SP, e o proximo disparo e' amanha as 8h
    de SP, que sao 11:00 UTC."""
    agora = datetime(2026, 7, 20, 23, 0, tzinfo=UTC)
    alvo = proxima_execucao(agora, 8)
    assert alvo == _sp(2026, 7, 21, 8)
    assert alvo.astimezone(UTC).hour == 11


def test_segundos_ate_proxima_bate_com_a_diferenca():
    agora = _sp(2026, 7, 20, 6, 0)
    assert segundos_ate_proxima(agora, 8) == 2 * 3600


def test_segundos_nunca_negativo():
    for hora_agora in range(24):
        agora = _sp(2026, 7, 20, hora_agora, 30)
        assert segundos_ate_proxima(agora, 8) > 0
