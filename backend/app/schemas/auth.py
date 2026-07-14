from pydantic import BaseModel, Field
from typing import Optional


class LoginRequest(BaseModel):
    email: str
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
    email: str
    funcao_id: Optional[int]
    funcao: Optional[str] = None

    model_config = {"from_attributes": True}


class PortalLoginRequest(BaseModel):
    documento: str
    login: str
    senha: str


class TrocarSenhaIn(BaseModel):
    senha_atual: str
    nova_senha: str = Field(min_length=8)


class LoginOut(BaseModel):
    precisa_redefinir: bool = False
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"


class DefinirSenhaIn(BaseModel):
    email: str
    senha_atual: str
    nova_senha: str = Field(min_length=8)


class DefinirSenhaPortalIn(BaseModel):
    documento: str
    login: str
    senha_atual: str
    nova_senha: str = Field(min_length=8)
