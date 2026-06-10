from pydantic import BaseModel
from typing import Optional, Literal
from datetime import date, datetime


class FrotaListOut(BaseModel):
    id: int
    cliente: int
    cliente_nome: Optional[str] = None
    equipamento: int
    equipamento_descricao: Optional[str] = None
    serie: Optional[str] = None
    patrimonio: Optional[str] = None
    prox_calibragem: Optional[date] = None
    ativo: bool
    status: str
    status_calibracao: str
    model_config = {"from_attributes": True}


class FrotaPage(BaseModel):
    items: list[FrotaListOut]
    total: int


class EquipamentoClienteOut(BaseModel):
    id: int
    cliente: int
    cliente_nome: Optional[str] = None
    equipamento: int
    equipamento_descricao: Optional[str] = None
    modulo: int
    serie: Optional[str] = None
    patrimonio: Optional[str] = None
    datacompra: Optional[date] = None
    ult_calibragem: Optional[date] = None
    prox_calibragem: Optional[date] = None
    ativo: bool
    status: str
    status_calibracao: str
    os_atual: Optional[int] = None
    calib_cert: Optional[str] = None
    calib_temp: Optional[str] = None
    calib_pressao: Optional[str] = None
    calib_teste1: Optional[str] = None
    calib_teste2: Optional[str] = None
    calib_teste3: Optional[str] = None
    calib_teste_media: Optional[str] = None
    calib_situacao: Optional[str] = None
    model_config = {"from_attributes": True}


class EquipamentoClienteCreate(BaseModel):
    cliente: int
    equipamento: int
    modulo: int = 0
    serie: Optional[str] = None
    patrimonio: Optional[str] = None
    datacompra: Optional[date] = None
    ult_calibragem: Optional[date] = None
    prox_calibragem: Optional[date] = None
    ativo: bool = True
    status: Literal["A", "I", "M"] = "A"


class EquipamentoClienteUpdate(BaseModel):
    equipamento: Optional[int] = None
    modulo: Optional[int] = None
    serie: Optional[str] = None
    patrimonio: Optional[str] = None
    datacompra: Optional[date] = None
    ult_calibragem: Optional[date] = None
    prox_calibragem: Optional[date] = None
    ativo: Optional[bool] = None
    status: Optional[Literal["A", "I", "M"]] = None


class HistoricoOut(BaseModel):
    id: int
    equipamento_cliente: int
    datamov: Optional[date] = None
    saida: Optional[int] = None
    entrada: Optional[int] = None
    model_config = {"from_attributes": True}


class EquipCertItem(BaseModel):
    os: int
    tipo: str
    data_geracao: datetime | None = None
    model_config = {"from_attributes": True}
