from datetime import datetime
from pydantic import BaseModel, ConfigDict


class SolicitarIn(BaseModel):
    equipamento_cliente: int
    obs: str | None = None


class PortalSolicitacaoItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    equipamento_cliente: int
    equipamento_descricao: str | None = None
    status: str
    data_solicitacao: datetime | None = None
    data_atendimento: datetime | None = None


class PortalSolicitacaoPage(BaseModel):
    items: list[PortalSolicitacaoItem]
    total: int


class SolicitacaoItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cliente: int
    cliente_nome: str | None = None
    equipamento_cliente: int
    equipamento_descricao: str | None = None
    status: str
    data_solicitacao: datetime | None = None
    data_atendimento: datetime | None = None
    atendido_por: int | None = None
    atendido_por_nome: str | None = None
    obs: str | None = None


class SolicitacaoPage(BaseModel):
    items: list[SolicitacaoItem]
    total: int
