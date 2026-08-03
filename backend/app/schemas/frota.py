from pydantic import BaseModel
from typing import Optional
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
    status_calibracao: str
    model_config = {"from_attributes": True}


class FrotaPage(BaseModel):
    items: list[FrotaListOut]
    total: int


class EloModuloOut(BaseModel):
    id: int
    serie: Optional[str] = None
    entrou_em: Optional[date] = None
    origem: Optional[str] = None
    model_config = {"from_attributes": True}


class EloPhoebusOut(BaseModel):
    id: int
    serie: Optional[str] = None
    cliente_nome: Optional[str] = None
    entrou_em: Optional[date] = None
    origem: Optional[str] = None
    model_config = {"from_attributes": True}


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
    status_calibracao: str
    os_atual: Optional[int] = None
    calib_cert: Optional[str] = None
    calib_temp: Optional[str] = None
    calib_pressao: Optional[str] = None
    calib_teste1: Optional[str] = None
    calib_teste2: Optional[str] = None
    calib_teste3: Optional[str] = None
    calib_teste4: Optional[str] = None
    calib_teste5: Optional[str] = None
    calib_teste_media: Optional[str] = None
    calib_situacao: Optional[str] = None
    modulo_instalado: Optional[EloModuloOut] = None
    instalado_em: Optional[EloPhoebusOut] = None
    em_estoque: bool = False
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


class EquipamentoClienteUpdate(BaseModel):
    equipamento: Optional[int] = None
    modulo: Optional[int] = None
    serie: Optional[str] = None
    patrimonio: Optional[str] = None
    datacompra: Optional[date] = None
    ult_calibragem: Optional[date] = None
    prox_calibragem: Optional[date] = None
    ativo: Optional[bool] = None


class HistoricoOut(BaseModel):
    id: int
    equipamento_cliente: int
    datamov: Optional[date] = None
    saida: Optional[int] = None
    entrada: Optional[int] = None
    model_config = {"from_attributes": True}


class EquipCertItem(BaseModel):
    os: int | None = None          # nulo no certificado de venda (nao ha OS)
    tipo: str
    data_geracao: datetime | None = None
    origem: str = "os"             # "os" | "venda"
    model_config = {"from_attributes": True}


class TransferirIn(BaseModel):
    cliente: int
    obs: Optional[str] = None


class TransferenciaOut(BaseModel):
    id: int
    equipamento_cliente: int
    de_cliente: int
    de_cliente_nome: Optional[str] = None
    para_cliente: int
    para_cliente_nome: Optional[str] = None
    usuario: Optional[int] = None
    usuario_nome: Optional[str] = None
    data: datetime
    obs: Optional[str] = None
    model_config = {"from_attributes": True}
