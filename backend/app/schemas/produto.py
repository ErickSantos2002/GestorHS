from typing import Optional
from pydantic import BaseModel, Field


class ProdutoOut(BaseModel):
    id: int
    sku: Optional[str] = None
    nome: str
    descricao: Optional[str] = None
    unidade: Optional[str] = None
    preco: float = 0
    ncm: Optional[str] = None
    ativo: bool = True
    model_config = {"from_attributes": True}


class ProdutoCreate(BaseModel):
    nome: str = Field(min_length=1)
    sku: Optional[str] = None
    descricao: Optional[str] = None
    unidade: Optional[str] = None
    preco: float = 0
    ncm: Optional[str] = None
    ativo: bool = True


class ProdutoUpdate(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=1)
    sku: Optional[str] = None
    descricao: Optional[str] = None
    unidade: Optional[str] = None
    preco: Optional[float] = None
    ncm: Optional[str] = None
    ativo: Optional[bool] = None
