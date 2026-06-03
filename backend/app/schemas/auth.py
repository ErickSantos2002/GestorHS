from pydantic import BaseModel, Field
from typing import Optional


class LoginRequest(BaseModel):
    login: str
    senha: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UsuarioOut(BaseModel):
    id: int
    nome: Optional[str]
    login: str
    email: Optional[str]
    funcao_id: Optional[int]
    funcao: Optional[str] = None

    model_config = {"from_attributes": True}


class PortalLoginRequest(BaseModel):
    cliente: int
    login: str
    senha: str


class TrocarSenhaIn(BaseModel):
    senha_atual: str
    nova_senha: str = Field(min_length=8)
