import re
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional
from datetime import date

# Colunas de largura FIXA em `clientes`. Um caractere a mais (um espaco colado
# junto no paste, por exemplo) estoura o INSERT e derruba a request com 500.
_SO_DIGITOS = {"cgc": 14, "cpf": 11, "cep": 8}
_TAMANHO_MAXIMO = {"estado": 2}


class _ClienteSaneado(BaseModel):
    """Limpa o que o usuario digita antes de encostar no banco.

    `str_strip_whitespace` mata o espaco sobrando em TODOS os campos de texto —
    era o que quebrava o cadastro, e o mesmo espaco em `email` passava batido e
    ia sujar o contato do cliente.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    # check_fields=False: os campos sao declarados nas subclasses, nao aqui
    @field_validator("cgc", "cpf", "cep", mode="after", check_fields=False)
    @classmethod
    def _apenas_digitos(cls, v: Optional[str], info) -> Optional[str]:
        if v is None:
            return None
        digitos = re.sub(r"\D", "", v)
        if not digitos:
            return None
        limite = _SO_DIGITOS[info.field_name]
        if len(digitos) > limite:
            raise ValueError(f"deve ter no maximo {limite} digitos")
        return digitos

    @field_validator("estado", mode="after", check_fields=False)
    @classmethod
    def _dentro_do_limite(cls, v: Optional[str], info) -> Optional[str]:
        if v is None or v == "":
            return None
        limite = _TAMANHO_MAXIMO[info.field_name]
        if len(v) > limite:
            raise ValueError(f"deve ter no maximo {limite} caracteres")
        return v


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


class ClienteCreate(_ClienteSaneado):
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


class ClienteUpdate(_ClienteSaneado):
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


class FuncionarioOut(BaseModel):
    id: int
    cliente: int
    setor: Optional[int] = None
    matricula: Optional[str] = None
    centro: Optional[str] = None
    nome: Optional[str] = None
    email: Optional[str] = None
    cargo: Optional[str] = None
    admissao: Optional[date] = None
    idade: Optional[int] = None
    sexo: Optional[str] = None
    estado: Optional[str] = None
    cidade: Optional[str] = None
    ativo: bool
    model_config = {"from_attributes": True}


class FuncionarioCreate(BaseModel):
    nome: str = Field(min_length=1)
    setor: Optional[int] = None
    matricula: Optional[str] = None
    centro: Optional[str] = None
    email: Optional[str] = None
    cargo: Optional[str] = None
    admissao: Optional[date] = None
    idade: Optional[int] = None
    sexo: Optional[str] = None
    estado: Optional[str] = None
    cidade: Optional[str] = None
    ativo: bool = True


class FuncionarioUpdate(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=1)
    setor: Optional[int] = None
    matricula: Optional[str] = None
    centro: Optional[str] = None
    email: Optional[str] = None
    cargo: Optional[str] = None
    admissao: Optional[date] = None
    idade: Optional[int] = None
    sexo: Optional[str] = None
    estado: Optional[str] = None
    cidade: Optional[str] = None
    ativo: Optional[bool] = None
