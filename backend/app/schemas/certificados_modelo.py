from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ModeloItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    equipamento: int
    equipamento_descricao: str | None = None
    tem_calibracao: bool = False
    tem_manutencao: bool = False


class ModeloPage(BaseModel):
    items: list[ModeloItem]


class CertificadoModeloOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    equipamento: int
    equipamento_descricao: str | None = None
    tipo: str = "C"
    descricao: str | None = None
    texto: str = ""


class CertificadoModeloIn(BaseModel):
    descricao: str | None = None
    texto: str


class ImagemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str | None = None
    arquivo: str
    url: str


class ImagemPage(BaseModel):
    items: list[ImagemOut]


class OSCertificadoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    tipo: str
    html: str | None = None
    pdf: str | None = None
    data_geracao: datetime | None = None
