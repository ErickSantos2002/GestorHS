"""Calculo de quando disparar um job diario. Puro, sem I/O e sem dormir.

Separado do laco que de fato espera para que a regra de horario — a parte com
armadilha — possa ser testada sem relogio nem sleep.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# O container roda em UTC; o horario do job e' o de operacao da Health Safety.
# Fixar o fuso aqui evita que "08:00" vire 05:00 da manha para quem trabalha.
TZ_SP = ZoneInfo("America/Sao_Paulo")


def proxima_execucao(agora: datetime, hora: int, minuto: int = 0) -> datetime:
    """O proximo `hora:minuto` no fuso de Sao Paulo, sempre no FUTURO.

    `agora` pode vir em qualquer fuso (o app roda em UTC) — e convertido antes de
    comparar. Quando o horario ja passou, ou e' exatamente agora, vai para o dia
    seguinte: um restart exatamente as 08:00:00 nao deve disparar o job de novo no
    mesmo instante.
    """
    agora_sp = agora.astimezone(TZ_SP)
    alvo = agora_sp.replace(hour=hora, minute=minuto, second=0, microsecond=0)
    if alvo <= agora_sp:
        alvo += timedelta(days=1)
    return alvo


def segundos_ate_proxima(agora: datetime, hora: int, minuto: int = 0) -> float:
    """Quantos segundos dormir ate o proximo disparo. Sempre > 0."""
    return (proxima_execucao(agora, hora, minuto) - agora.astimezone(TZ_SP)).total_seconds()
