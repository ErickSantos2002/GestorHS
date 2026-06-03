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


class CategoriaOut(BaseModel):
    id: int
    descricao: Optional[str] = None
    setor: Optional[int] = None
    posicao: int
    model_config = {"from_attributes": True}


class CategoriaCreate(BaseModel):
    descricao: str = Field(min_length=1)
    setor: Optional[int] = None
    posicao: int = 0


class CategoriaUpdate(BaseModel):
    descricao: Optional[str] = Field(default=None, min_length=1)
    setor: Optional[int] = None
    posicao: Optional[int] = None


class EquipamentoOut(BaseModel):
    id: int
    descricao: Optional[str] = None
    categoria: Optional[int] = None
    marca: Optional[int] = None
    detalhes: Optional[str] = None
    especificacao: Optional[str] = None
    preco_cod: float = 0
    preco_por: float = 0
    custo: float = 0
    peso_calibragem: float = 0
    peso: float = 0
    estoque: int = 0
    estoque_min: int = 0
    ativo: bool = False
    destaque: bool = False
    model_config = {"from_attributes": True}


class EquipamentoCreate(BaseModel):
    descricao: str = Field(min_length=1)
    categoria: Optional[int] = None
    marca: Optional[int] = None
    detalhes: Optional[str] = None
    especificacao: Optional[str] = None
    preco_cod: float = 0
    preco_por: float = 0
    custo: float = 0
    peso_calibragem: float = 0
    peso: float = 0
    estoque: int = 0
    estoque_min: int = 0
    ativo: bool = False
    destaque: bool = False


class EquipamentoUpdate(BaseModel):
    descricao: Optional[str] = Field(default=None, min_length=1)
    categoria: Optional[int] = None
    marca: Optional[int] = None
    detalhes: Optional[str] = None
    especificacao: Optional[str] = None
    preco_cod: Optional[float] = None
    preco_por: Optional[float] = None
    custo: Optional[float] = None
    peso_calibragem: Optional[float] = None
    peso: Optional[float] = None
    estoque: Optional[int] = None
    estoque_min: Optional[int] = None
    ativo: Optional[bool] = None
    destaque: Optional[bool] = None
