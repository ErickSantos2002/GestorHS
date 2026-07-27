from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.agendamento import TZ_SP, proxima_execucao_mensal, segundos_ate_proxima_mensal

UTC = ZoneInfo("UTC")


def _sp(ano, mes, dia, hora, minuto=0):
    return datetime(ano, mes, dia, hora, minuto, tzinfo=TZ_SP)


def test_no_meio_do_mes_agenda_para_o_dia_1_seguinte():
    agora = _sp(2026, 7, 20, 10, 0)
    assert proxima_execucao_mensal(agora, 8) == _sp(2026, 8, 1, 8)


def test_no_dia_1_antes_da_hora_agenda_para_hoje():
    agora = _sp(2026, 8, 1, 6, 30)
    assert proxima_execucao_mensal(agora, 8) == _sp(2026, 8, 1, 8)


def test_no_dia_1_depois_da_hora_agenda_para_o_mes_seguinte():
    agora = _sp(2026, 8, 1, 9, 15)
    assert proxima_execucao_mensal(agora, 8) == _sp(2026, 9, 1, 8)


def test_exatamente_no_horario_agenda_para_o_mes_seguinte():
    """Um restart as 08:00:00 do dia 1 nao pode redisparar a rodada no mesmo instante."""
    agora = _sp(2026, 8, 1, 8, 0)
    assert proxima_execucao_mensal(agora, 8) == _sp(2026, 9, 1, 8)


def test_vira_o_ano():
    agora = _sp(2026, 12, 15, 10, 0)
    assert proxima_execucao_mensal(agora, 8) == _sp(2027, 1, 1, 8)


def test_atravessa_fevereiro():
    """Fevereiro tem 28/29 dias; o alvo e' sempre o dia 1, entao a virada nao depende
    do tamanho do mes — este teste trava isso contra uma implementacao com timedelta."""
    assert proxima_execucao_mensal(_sp(2026, 1, 20, 10, 0), 8) == _sp(2026, 2, 1, 8)
    assert proxima_execucao_mensal(_sp(2026, 2, 15, 10, 0), 8) == _sp(2026, 3, 1, 8)
    assert proxima_execucao_mensal(_sp(2028, 2, 29, 10, 0), 8) == _sp(2028, 3, 1, 8)


def test_horario_e_o_de_sao_paulo_nao_utc():
    """O container roda em UTC. 23:00 UTC = 20:00 em SP, entao o disparo e' as 8h de
    SP do dia 1, que sao 11:00 UTC."""
    agora = datetime(2026, 7, 31, 23, 0, tzinfo=UTC)
    alvo = proxima_execucao_mensal(agora, 8)
    assert alvo == _sp(2026, 8, 1, 8)
    assert alvo.astimezone(UTC).hour == 11


def test_segundos_bate_com_a_diferenca():
    agora = _sp(2026, 8, 1, 6, 0)
    assert segundos_ate_proxima_mensal(agora, 8) == 2 * 3600


def test_segundos_nunca_negativo():
    for hora_agora in range(24):
        agora = _sp(2026, 8, 1, hora_agora, 30)
        assert segundos_ate_proxima_mensal(agora, 8) > 0
