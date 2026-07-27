"""Calculo de quando disparar o job mensal. Puro, sem I/O e sem dormir.

Separado do laco que de fato espera para que a regra de horario — a parte com
armadilha — possa ser testada sem relogio nem sleep.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

# O container roda em UTC; o horario do job e' o de operacao da Health Safety.
# Fixar o fuso aqui evita que "08:00" vire 05:00 da manha para quem trabalha.
TZ_SP = ZoneInfo("America/Sao_Paulo")


def proxima_execucao_mensal(agora: datetime, hora: int, minuto: int = 0) -> datetime:
    """O proximo dia 1 as `hora:minuto` no fuso de Sao Paulo, sempre no FUTURO.

    `agora` pode vir em qualquer fuso (o app roda em UTC) — e' convertido antes de
    comparar. Quando o horario ja passou, ou e' exatamente agora, vai para o mes
    seguinte: um restart exatamente as 08:00:00 do dia 1 nao deve disparar a rodada
    de novo no mesmo instante.

    O alvo e' sempre o dia 1, entao avancar o mes nunca cai em data invalida — e a
    conta nao depende de quantos dias o mes tem (nada de somar 30 dias).
    """
    agora_sp = agora.astimezone(TZ_SP)
    alvo = agora_sp.replace(day=1, hour=hora, minute=minuto, second=0, microsecond=0)
    if alvo <= agora_sp:
        if alvo.month == 12:
            alvo = alvo.replace(year=alvo.year + 1, month=1)
        else:
            alvo = alvo.replace(month=alvo.month + 1)
    return alvo


def segundos_ate_proxima_mensal(agora: datetime, hora: int, minuto: int = 0) -> float:
    """Quantos segundos dormir ate o proximo disparo. Sempre > 0."""
    return (proxima_execucao_mensal(agora, hora, minuto)
            - agora.astimezone(TZ_SP)).total_seconds()
