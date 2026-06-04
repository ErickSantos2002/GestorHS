from pydantic import BaseModel


class PortalMeOut(BaseModel):
    id: int
    login: str
    nome: str | None = None
    cliente: int
    cliente_nome: str | None = None


class PortalResumoOut(BaseModel):
    aparelhos: int
    vencidos: int
    os_andamento: int
