from pydantic import BaseModel, Field
from typing import Optional
from datetime import date


class ClienteListOut(BaseModel):
    id: int
    nome: Optional[str] = None
    cgc: Optional[str] = None
    cpf: Optional[str] = None
    municipio: Optional[str] = None
    estado: Optional[str] = None
    ativo: bool
    model_config = {"from_attributes": True}


class ClientesPage(BaseModel):
    items: list[ClienteListOut]
    total: int


class ClienteOut(BaseModel):
    id: int
    grupo: Optional[int] = None
    nome: Optional[str] = None
    cgc: Optional[str] = None
    cpf: Optional[str] = None
    endereco: Optional[str] = None
    numero: Optional[int] = None
    complemento: Optional[str] = None
    bairro: Optional[str] = None
    municipio: Optional[str] = None
    estado: Optional[str] = None
    cep: Optional[str] = None
    contato: Optional[str] = None
    email: Optional[str] = None
    telefones: Optional[str] = None
    celular: Optional[str] = None
    whatsapp: Optional[str] = None
    whatsapp1: Optional[str] = None
    whatsapp2: Optional[str] = None
    insc_mun: Optional[str] = None
    insc_est: Optional[str] = None
    datcad: Optional[date] = None
    obs: Optional[str] = None
    ativo: bool
    model_config = {"from_attributes": True}


class ClienteCreate(BaseModel):
    nome: str = Field(min_length=1)
    grupo: Optional[int] = None
    cgc: Optional[str] = None
    cpf: Optional[str] = None
    endereco: Optional[str] = None
    numero: Optional[int] = None
    complemento: Optional[str] = None
    bairro: Optional[str] = None
    municipio: Optional[str] = None
    estado: Optional[str] = None
    cep: Optional[str] = None
    contato: Optional[str] = None
    email: Optional[str] = None
    telefones: Optional[str] = None
    celular: Optional[str] = None
    whatsapp: Optional[str] = None
    whatsapp1: Optional[str] = None
    whatsapp2: Optional[str] = None
    insc_mun: Optional[str] = None
    insc_est: Optional[str] = None
    obs: Optional[str] = None
    ativo: bool = True


class ClienteUpdate(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=1)
    grupo: Optional[int] = None
    cgc: Optional[str] = None
    cpf: Optional[str] = None
    endereco: Optional[str] = None
    numero: Optional[int] = None
    complemento: Optional[str] = None
    bairro: Optional[str] = None
    municipio: Optional[str] = None
    estado: Optional[str] = None
    cep: Optional[str] = None
    contato: Optional[str] = None
    email: Optional[str] = None
    telefones: Optional[str] = None
    celular: Optional[str] = None
    whatsapp: Optional[str] = None
    whatsapp1: Optional[str] = None
    whatsapp2: Optional[str] = None
    insc_mun: Optional[str] = None
    insc_est: Optional[str] = None
    obs: Optional[str] = None
    ativo: Optional[bool] = None
