from pydantic import BaseModel, Field, EmailStr
from typing import Optional


class FuncaoOut(BaseModel):
    id: int
    descricao: str
    model_config = {"from_attributes": True}


class UsuarioListOut(BaseModel):
    id: int
    nome: Optional[str]
    email: str
    funcao_id: Optional[int]
    funcao: Optional[str] = None
    precisa_redefinir_senha: bool
    ativo: bool
    model_config = {"from_attributes": True}


class UsuarioCreate(BaseModel):
    nome: Optional[str] = None
    email: EmailStr
    senha: str = Field(min_length=8)
    funcao_id: Optional[int] = None


class UsuarioUpdate(BaseModel):
    nome: Optional[str] = None
    email: Optional[EmailStr] = None
    funcao_id: Optional[int] = None


class RedefinirSenhaIn(BaseModel):
    nova_senha: str = Field(min_length=8)
