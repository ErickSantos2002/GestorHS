import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EmpresaIn(BaseModel):
    """Criacao e edicao (PUT substitui tudo). `documento` aceita mascara; a
    validacao do digito verificador fica no servico, que devolve 422 proprio."""
    model_config = ConfigDict(str_strip_whitespace=True)

    documento: str
    cliente: Optional[int] = None
    nome: str = Field(min_length=1, max_length=100)
    cep: Optional[str] = Field(default=None, max_length=9)
    endereco: Optional[str] = Field(default=None, max_length=100)
    numero: Optional[str] = Field(default=None, max_length=20)
    complemento: Optional[str] = Field(default=None, max_length=60)
    bairro: Optional[str] = Field(default=None, max_length=100)
    municipio: Optional[str] = Field(default=None, max_length=100)
    estado: Optional[str] = Field(default=None, max_length=2)
    email: Optional[str] = Field(default=None, max_length=100)
    telefone: Optional[str] = Field(default=None, max_length=50)
    insc_est: Optional[str] = Field(default=None, max_length=20)

    @field_validator("cep", "endereco", "numero", "complemento", "bairro", "municipio",
                     "estado", "email", "telefone", "insc_est", mode="after")
    @classmethod
    def _vazio_vira_none(cls, v: Optional[str], info) -> Optional[str]:
        if v is None or v == "":
            return None
        if info.field_name == "cep":
            d = re.sub(r"\D", "", v)
            return d[:8] or None
        if info.field_name == "estado":
            return v.upper()
        return v


class EmpresaOut(BaseModel):
    id: int
    cliente: Optional[int] = None
    matriz_nome: Optional[str] = None
    nome: str
    cgc: Optional[str] = None
    cpf: Optional[str] = None
    cep: Optional[str] = None
    endereco: Optional[str] = None
    numero: Optional[str] = None
    complemento: Optional[str] = None
    bairro: Optional[str] = None
    municipio: Optional[str] = None
    estado: Optional[str] = None
    email: Optional[str] = None
    telefone: Optional[str] = None
    insc_est: Optional[str] = None
    ativo: bool
    tiny_id: Optional[int] = None
    tiny_status: Optional[str] = None
    tiny_erro: Optional[str] = None
    tiny_em: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class EmpresasPage(BaseModel):
    items: list[EmpresaOut]
    total: int
