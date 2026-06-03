from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class OrdemListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cliente: int
    cliente_nome: str | None = None
    equipamento_cliente: int | None = None
    equipamento_descricao: str | None = None
    equipamento_serie: str | None = None
    fase: int | None = None
    fase_descricao: str | None = None
    fase_cor: str | None = None
    tipo_servico: str | None = None
    data_chegada: datetime | None = None
    prox_calibragem: datetime | None = None
    situacao: str


class OrdemPage(BaseModel):
    items: list[OrdemListOut]
    total: int


class QuadroColuna(BaseModel):
    fase: int
    descricao: str
    cor: str
    ordens: list[OrdemListOut]


class OrdemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cliente: int
    cliente_nome: str | None = None
    equipamento_cliente: int | None = None
    equipamento_descricao: str | None = None
    equipamento_serie: str | None = None
    fase: int | None = None
    fase_descricao: str | None = None
    fase_cor: str | None = None
    tipo_servico: str | None = None
    condicao_chegada: str | None = None
    acessorios: str | None = None
    aceite: bool
    recebido: bool
    situacao: str
    etiqueta: str | None = None
    cod_retorno: str | None = None
    obs: str | None = None
    data_chegada: datetime | None = None
    data_calibracao: datetime | None = None
    data_retorno: datetime | None = None
    data_aceite: datetime | None = None
    prox_calibragem: datetime | None = None
    # espelho (preenchidos na 3E — só leitura)
    calib_cert: str | None = None
    calib_temp: str | None = None
    calib_pressao: str | None = None
    calib_teste_media: str | None = None
    calib_situacao: str | None = None
    pdf_certificado: str | None = None


class OrdemAbrirIn(BaseModel):
    equipamento_cliente: int
    tipo_servico: Literal["C", "M", "A"]
    condicao_chegada: str | None = None
    acessorios: str | None = None


class AvancarIn(BaseModel):
    obs: str | None = None
    cod_retorno: str | None = None


class CancelarIn(BaseModel):
    motivo: str = Field(min_length=1)


class LogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    os: int
    usuario: int | None = None
    autor: str
    datalog: datetime | None = None
    texto: str | None = None


class TipoCalibragemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    descricao: str
