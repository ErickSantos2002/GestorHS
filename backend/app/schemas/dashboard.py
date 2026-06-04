from pydantic import BaseModel


class OsPorFaseItem(BaseModel):
    fase: int
    descricao: str
    cor: str
    total: int


class DashboardOut(BaseModel):
    aparelhos_vencidos: int
    aparelhos_vencendo: int
    solicitacoes_pendentes: int
    clientes_a_cobrar: int
    os_por_fase: list[OsPorFaseItem]
