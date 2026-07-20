from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


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


class PortalFrotaItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    equipamento_descricao: str | None = None
    serie: str | None = None
    patrimonio: str | None = None
    prox_calibragem: date | None = None
    status_calibracao: str


class PortalFrotaPage(BaseModel):
    items: list[PortalFrotaItem]
    total: int


class PortalCertItem(BaseModel):
    equipamento_cliente: int
    equipamento_descricao: str | None = None
    serie: str | None = None
    calib_cert: str | None = None
    ult_calibragem: date | None = None
    prox_calibragem: date | None = None
    pdf: str | None = None
    os: int | None = None
    venda: bool = False        # PDF vem do certificado de venda (aparelho sem OS)


class PortalCertPage(BaseModel):
    items: list[PortalCertItem]
    total: int


class PortalOSItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    equipamento_descricao: str | None = None
    equipamento_serie: str | None = None
    fase: int | None = None
    fase_descricao: str | None = None
    fase_cor: str | None = None
    tipo_servico: str | None = None
    data_chegada: datetime | None = None
    prox_calibragem: datetime | None = None
    situacao: str


class PortalOSPage(BaseModel):
    items: list[PortalOSItem]
    total: int
