from datetime import date, datetime
from pydantic import BaseModel


class AlertaItem(BaseModel):
    cliente: int
    cliente_nome: str | None = None
    vencidos: int
    vencendo: int
    prox_antiga: date | None = None
    ult_contato: datetime | None = None


class AlertaPage(BaseModel):
    items: list[AlertaItem]
    total: int


class ContatoOut(BaseModel):
    cliente: int
    atualizados: int
    ult_contato: datetime | None = None
