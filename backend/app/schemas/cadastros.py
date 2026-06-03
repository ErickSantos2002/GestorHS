from pydantic import BaseModel, Field
from typing import Optional


class SetorOut(BaseModel):
    id: int
    descricao: str
    model_config = {"from_attributes": True}


class SetorCreate(BaseModel):
    descricao: str = Field(min_length=1)


class SetorUpdate(BaseModel):
    descricao: Optional[str] = Field(default=None, min_length=1)


class MarcaOut(BaseModel):
    id: int
    descricao: str
    imagem: Optional[str] = None
    model_config = {"from_attributes": True}


class MarcaCreate(BaseModel):
    descricao: str = Field(min_length=1)


class MarcaUpdate(BaseModel):
    descricao: Optional[str] = Field(default=None, min_length=1)


class GrupoOut(BaseModel):
    id: int
    descricao: str
    texto: Optional[str] = None
    model_config = {"from_attributes": True}


class GrupoCreate(BaseModel):
    descricao: str = Field(min_length=1)
    texto: Optional[str] = None


class GrupoUpdate(BaseModel):
    descricao: Optional[str] = Field(default=None, min_length=1)
    texto: Optional[str] = None
