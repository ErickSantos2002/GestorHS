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


def proxima_calibracao(ult: Optional[date]) -> Optional[date]:
    """Data da proxima calibracao: 1 ano depois da ultima.

    Regra unica do negocio — nao ha periodicidade por aparelho. Confirmada nos
    dados vindos do sistema antigo, onde 9.108 OS usam exatamente 365/366 dias.

    Ficou de fora do GestorHS ate 08/2026: a coluna existia, mas nada a
    preenchia, entao todo aparelho calibrado aqui mantinha a data do ciclo
    anterior e escorregava para "Vencido" mesmo recem-calibrado.
    """
    if ult is None:
        return None
    try:
        return ult.replace(year=ult.year + 1)
    except ValueError:
        # 29/02 -> o ano seguinte nao e bissexto; vence em 28/02.
        return ult.replace(year=ult.year + 1, day=28)
