from datetime import date
from pydantic import BaseModel, ConfigDict


class CaixaCreate(BaseModel):
    obs: str | None = None


class CaixaUpdate(BaseModel):
    obs: str | None = None


class OrdemResumoCaixa(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cliente: int
    cliente_nome: str | None = None
    equipamento_descricao: str | None = None
    equipamento_serie: str | None = None
    fase: int | None = None
    fase_descricao: str | None = None
    fase_cor: str | None = None
    desfecho_lab: str = "pendente"
    desfecho_lab_obs: str | None = None


class CaixaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    data: date | None = None
    obs: str | None = None
    fase: int | None = None
    fase_descricao: str | None = None
    fase_cor: str | None = None
    total_os: int = 0
    clientes: list[str] = []
    cliente_principal: int | None = None


class CaixaDetalhe(CaixaOut):
    ordens: list[OrdemResumoCaixa] = []


class CaixaPage(BaseModel):
    items: list[CaixaOut]
    total: int


class VincularOrdemIn(BaseModel):
    ordem_id: int


class CaixaQuadroItem(BaseModel):
    id: int
    cliente_nome: str | None = None
    total_os: int
    prontos: int
    pendentes: int


class QuadroCaixaColuna(BaseModel):
    fase: int
    descricao: str
    cor: str
    total: int
    caixas: list[CaixaQuadroItem]
