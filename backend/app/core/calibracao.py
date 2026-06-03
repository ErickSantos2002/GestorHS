from datetime import date, timedelta
from typing import Optional


def status_calibracao(prox: Optional[date], hoje: date, dias: int = 90) -> str:
    """Classifica a próxima calibração: sem_data | vencido | vencendo | em_dia."""
    if prox is None:
        return "sem_data"
    if prox < hoje:
        return "vencido"
    if prox <= hoje + timedelta(days=dias):
        return "vencendo"
    return "em_dia"
