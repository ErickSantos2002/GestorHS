from datetime import datetime, timezone
import sqlalchemy as sa
from sqlalchemy import (Column, Integer, String, Text, Numeric, Date, DateTime,
                        ForeignKey, Boolean, JSON)
from sqlalchemy.orm import relationship
from app.models.database import Base


class Proposta(Base):
    __tablename__ = "propostas"
    id = Column(Integer, primary_key=True, index=True)
    numero = Column(Integer, nullable=False, unique=True, index=True)
    cliente = Column(Integer, ForeignKey("clientes.id", ondelete="SET NULL"), nullable=True, index=True)
    contato = Column(String(255), nullable=True)         # "aos cuidados de"
    vendedor = Column(String(255), nullable=True)        # = criador, imutavel
    data = Column(Date, nullable=True)
    intro = Column(Text, nullable=True)
    outros_itens = Column(Text, nullable=True)           # HTML do editor rico
    desconto = Column(Numeric(12, 2), nullable=False, default=0)
    frete = Column(Numeric(12, 2), nullable=False, default=0)
    forma_envio = Column(String(100), nullable=True)
    forma_frete = Column(String(100), nullable=True)
    transportador = Column(String(255), nullable=True)
    condicao_pagamento = Column(String(255), nullable=True)
    validade_dias = Column(Integer, nullable=True)
    data_entrega = Column(Date, nullable=True)
    descricao_entrega = Column(String(500), nullable=True)
    endereco_entrega_diferente = Column(Boolean, nullable=False, default=False)
    endereco_entrega = Column(JSON, nullable=True)
    cliente_override = Column(JSON, nullable=True)
    observacoes = Column(Text, nullable=True)
    assinatura = Column(String(255), nullable=True)
    faturada = Column(Boolean, nullable=False, default=False, server_default=sa.text("false"))
    faturada_em = Column(DateTime(timezone=True), nullable=True)
    faturada_por = Column(String(255), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    cliente_rel = relationship("Cliente", lazy="joined")
    itens = relationship("PropostaItem", back_populates="proposta_rel", cascade="all, delete-orphan", lazy="selectin")
    aparelhos = relationship("PropostaAparelho", back_populates="proposta_rel", cascade="all, delete-orphan", lazy="selectin")
    versoes = relationship("PropostaVersao", back_populates="proposta_rel", cascade="all, delete-orphan", lazy="selectin", order_by="PropostaVersao.numero_versao")


class PropostaItem(Base):
    __tablename__ = "proposta_itens"
    id = Column(Integer, primary_key=True, index=True)
    proposta = Column(Integer, ForeignKey("propostas.id", ondelete="CASCADE"), nullable=False, index=True)
    descricao = Column(String(500), nullable=False)
    sku = Column(String(100), nullable=True)
    quantidade = Column(Numeric(12, 4), nullable=False, default=1)
    unidade = Column(String(20), nullable=True)
    preco_un = Column(Numeric(12, 2), nullable=False, default=0)
    total = Column(Numeric(12, 2), nullable=False, default=0)
    proposta_rel = relationship("Proposta", back_populates="itens")


class PropostaAparelho(Base):
    __tablename__ = "proposta_aparelhos"
    id = Column(Integer, primary_key=True, index=True)
    proposta = Column(Integer, ForeignKey("propostas.id", ondelete="CASCADE"), nullable=False, index=True)
    equipamento_cliente = Column(Integer, ForeignKey("equipamentos_cliente.id", ondelete="SET NULL"), nullable=True)
    serie = Column(String(100), nullable=True)
    modelo = Column(String(255), nullable=True)
    patrimonio = Column(String(100), nullable=True)
    prox_calibragem = Column(Date, nullable=True)
    proposta_rel = relationship("Proposta", back_populates="aparelhos")
