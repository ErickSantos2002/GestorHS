from datetime import date as date_type
from typing import Optional

from pydantic import BaseModel


class ServicoIn(BaseModel):
    descricao: str
    resumo_padrao: str = ""
    ativo: bool = True


class ServicoUpdate(BaseModel):
    descricao: Optional[str] = None
    resumo_padrao: Optional[str] = None
    ativo: Optional[bool] = None


class ServicoOut(BaseModel):
    id: int
    descricao: str
    resumo_padrao: str
    ativo: bool
    model_config = {"from_attributes": True}


class ManutencaoItemOut(BaseModel):
    servico: int
    descricao: str
    resumo_padrao: str


class ManutencaoIn(BaseModel):
    numero: Optional[str] = None
    data_manutencao: Optional[date_type] = None
    resumo: Optional[str] = None
    servicos: list[int] = []          # ids do catalogo, NA ORDEM escolhida


class ManutencaoOut(BaseModel):
    id: int
    os: int
    numero: Optional[str] = None
    data_manutencao: Optional[date_type] = None
    resumo: Optional[str] = None
    servicos: list[ManutencaoItemOut] = []
    model_config = {"from_attributes": True}
