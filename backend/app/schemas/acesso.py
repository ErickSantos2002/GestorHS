from pydantic import BaseModel, Field
from typing import Optional


class FuncaoOut(BaseModel):
    id: int
    descricao: str
    model_config = {"from_attributes": True}


class UsuarioListOut(BaseModel):
    id: int
    nome: Optional[str]
    login: str
    email: Optional[str]
    funcao_id: Optional[int]
    funcao: Optional[str] = None
    precisa_redefinir_senha: bool
    model_config = {"from_attributes": True}


class UsuarioCreate(BaseModel):
    nome: Optional[str] = None
    login: str = Field(min_length=1, max_length=20)
    email: Optional[str] = None
    senha: str = Field(min_length=8)
    funcao_id: Optional[int] = None


class UsuarioUpdate(BaseModel):
    nome: Optional[str] = None
    email: Optional[str] = None
    funcao_id: Optional[int] = None
    login: Optional[str] = Field(default=None, min_length=1, max_length=20)


class RedefinirSenhaIn(BaseModel):
    nova_senha: str = Field(min_length=8)
