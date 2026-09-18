import re
from datetime import date as date_type, datetime
from typing import Literal, Optional, List
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PropostaItemBase(BaseModel):
    descricao: str
    sku: Optional[str] = None
    quantidade: float = 1
    unidade: Optional[str] = None
    preco_un: float = 0


class PropostaItemCreate(PropostaItemBase):
    pass


class PropostaItemOut(PropostaItemBase):
    id: int
    total: float
    model_config = {"from_attributes": True}


class PropostaAparelhoCreate(BaseModel):
    equipamento_cliente: int


class PropostaAparelhoOut(BaseModel):
    id: int
    equipamento_cliente: Optional[int] = None
    serie: Optional[str] = None
    modelo: Optional[str] = None
    patrimonio: Optional[str] = None
    prox_calibragem: Optional[date_type] = None
    model_config = {"from_attributes": True}


class DestinatarioIn(BaseModel):
    """Dados do destinatario como estao no modal. O servidor grava no cadastro
    (Cliente/Empresa) e monta a copia congelada a partir do cadastro salvo —
    este bloco NUNCA vai direto para `propostas.destinatario`."""
    model_config = ConfigDict(str_strip_whitespace=True)

    tipo: Literal["cliente", "empresa", "nova_empresa"]
    id: Optional[int] = None
    matriz: Optional[int] = None   # cliente matriz: vale em `empresa` e `nova_empresa`
    nome: str = Field(min_length=1, max_length=100)
    documento: Optional[str] = None
    cep: Optional[str] = Field(default=None, max_length=9)
    endereco: Optional[str] = Field(default=None, max_length=100)
    numero: Optional[str] = Field(default=None, max_length=20)
    complemento: Optional[str] = Field(default=None, max_length=60)
    bairro: Optional[str] = Field(default=None, max_length=100)
    municipio: Optional[str] = Field(default=None, max_length=100)
    estado: Optional[str] = Field(default=None, max_length=2)
    # Opcionais desde 18/09/2026: em branco quer dizer "nao mexe no cadastro", e
    # nao "apaga". Quem preserva e' `_aplicar_destinatario`; aqui so garantimos
    # que "" chega como None, para os dois virarem o mesmo caso.
    email: Optional[str] = Field(default=None, max_length=100)
    telefone: Optional[str] = Field(default=None, max_length=50)

    @field_validator("cep", "endereco", "numero", "complemento", "bairro", "municipio", "estado",
                     "email", "telefone", mode="after")
    @classmethod
    def _vazio_vira_none(cls, v: Optional[str], info) -> Optional[str]:
        if not v:
            return None
        if info.field_name == "cep":
            return re.sub(r"\D", "", v)[:8] or None
        if info.field_name == "estado":
            return v.upper()
        return v

    @model_validator(mode="after")
    def _coerente(self):
        if self.tipo == "nova_empresa":
            if not self.documento:
                raise ValueError("documento obrigatorio para cadastrar empresa")
        elif self.id is None:
            raise ValueError("id obrigatorio para cliente ou empresa existente")
        return self


class PropostaBase(BaseModel):
    contato: Optional[str] = None
    vendedor: Optional[str] = None
    data: Optional[date_type] = None
    intro: Optional[str] = None
    outros_itens: Optional[str] = None
    desconto: float = 0
    frete: float = 0
    forma_envio: Optional[str] = None
    forma_frete: Optional[str] = None
    transportador: Optional[str] = None
    condicao_pagamento: Optional[str] = None
    validade_dias: Optional[int] = None
    data_entrega: Optional[date_type] = None
    descricao_entrega: Optional[str] = None
    endereco_entrega_diferente: bool = False
    endereco_entrega: Optional[dict] = None
    observacoes: Optional[str] = None
    assinatura: Optional[str] = None


class PropostaCreate(PropostaBase):
    itens: List[PropostaItemCreate] = Field(default_factory=list)
    aparelhos: List[PropostaAparelhoCreate] = Field(default_factory=list)
    destinatario: Optional[DestinatarioIn] = None


class PropostaUpdate(BaseModel):
    # todos opcionais; se itens/aparelhos vierem, substituem a lista inteira
    contato: Optional[str] = None
    vendedor: Optional[str] = None
    data: Optional[date_type] = None
    intro: Optional[str] = None
    outros_itens: Optional[str] = None
    desconto: Optional[float] = None
    frete: Optional[float] = None
    forma_envio: Optional[str] = None
    forma_frete: Optional[str] = None
    transportador: Optional[str] = None
    condicao_pagamento: Optional[str] = None
    validade_dias: Optional[int] = None
    data_entrega: Optional[date_type] = None
    descricao_entrega: Optional[str] = None
    endereco_entrega_diferente: Optional[bool] = None
    endereco_entrega: Optional[dict] = None
    observacoes: Optional[str] = None
    assinatura: Optional[str] = None
    itens: Optional[List[PropostaItemCreate]] = None
    aparelhos: Optional[List[PropostaAparelhoCreate]] = None
    destinatario: Optional[DestinatarioIn] = None


class PropostaVersaoOut(BaseModel):
    id: int
    numero_versao: int
    alterado_por: Optional[str] = None
    created_at: Optional[datetime] = None
    has_pdf: bool = False
    snapshot: Optional[dict] = None
    model_config = {"from_attributes": True}


class PropostaOut(PropostaBase):
    id: int
    numero: int
    cliente: Optional[int] = None
    empresa: Optional[int] = None
    destinatario: Optional[dict] = None
    itens: List[PropostaItemOut] = Field(default_factory=list)
    aparelhos: List[PropostaAparelhoOut] = Field(default_factory=list)
    total_itens: float = 0
    total: float = 0
    cliente_nome: Optional[str] = None
    cliente_documento: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    faturada: bool = False
    faturada_em: Optional[datetime] = None
    faturada_por: Optional[str] = None
    # Desabilitada: fora de circulação, mas inteira no banco. Só Admin reativa.
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class PropostaListOut(BaseModel):
    items: List[PropostaOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class DestinatarioBuscaOut(BaseModel):
    tipo: Literal["cliente", "empresa"]
    id: int
    nome: Optional[str] = None
    documento: Optional[str] = None
    municipio: Optional[str] = None
    estado: Optional[str] = None
    matriz_id: Optional[int] = None
    matriz_nome: Optional[str] = None
