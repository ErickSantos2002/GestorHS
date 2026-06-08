from pydantic import BaseModel, ConfigDict


class ModeloItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    equipamento: int
    equipamento_descricao: str | None = None
    tem_certificado: bool = False


class ModeloPage(BaseModel):
    items: list[ModeloItem]


class CertificadoModeloOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    equipamento: int
    equipamento_descricao: str | None = None
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
