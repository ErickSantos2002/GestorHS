from datetime import date as date_type, datetime
from typing import Optional, List
from pydantic import BaseModel, Field


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


class PropostaBase(BaseModel):
    cliente: Optional[int] = None
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
    cliente_override: Optional[dict] = None
    observacoes: Optional[str] = None
    assinatura: Optional[str] = None


class PropostaCreate(PropostaBase):
    itens: List[PropostaItemCreate] = Field(default_factory=list)
    aparelhos: List[PropostaAparelhoCreate] = Field(default_factory=list)


class PropostaUpdate(BaseModel):
    # todos opcionais; se itens/aparelhos vierem, substituem a lista inteira
    cliente: Optional[int] = None
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
    cliente_override: Optional[dict] = None
    observacoes: Optional[str] = None
    assinatura: Optional[str] = None
    itens: Optional[List[PropostaItemCreate]] = None
    aparelhos: Optional[List[PropostaAparelhoCreate]] = None


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
    model_config = {"from_attributes": True}


class PropostaListOut(BaseModel):
    items: List[PropostaOut]
    total: int
    page: int
    page_size: int
    total_pages: int
