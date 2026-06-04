from pydantic import BaseModel, ConfigDict, Field


class UsuarioPortalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cliente: int
    login: str
    nome: str | None = None
    email: str | None = None
    precisa_redefinir_senha: bool


class UsuarioPortalCreate(BaseModel):
    login: str
    nome: str | None = None
    email: str | None = None
    senha: str = Field(min_length=8)


class UsuarioPortalUpdate(BaseModel):
    login: str | None = None
    nome: str | None = None
    email: str | None = None


class RedefinirSenhaClienteIn(BaseModel):
    nova_senha: str = Field(min_length=8)
