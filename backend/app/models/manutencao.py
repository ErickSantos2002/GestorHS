from datetime import datetime, timezone

from sqlalchemy import (Column, Integer, String, Text, Date, DateTime, Boolean,
                        ForeignKey, UniqueConstraint)
from sqlalchemy.orm import relationship

from app.models.database import Base


class ManutencaoServico(Base):
    """Catalogo FECHADO de servicos. O tecnico escolhe daqui, nao digita.

    Aposentar um servico e' desativar, nunca apagar: apagar faria relatorio
    antigo perder o registro do que foi feito.
    """
    __tablename__ = "manutencao_servicos"

    id = Column(Integer, primary_key=True, index=True)
    descricao = Column(String(200), nullable=False, unique=True)   # vai para "Tipo do Problema"
    resumo_padrao = Column(Text, nullable=False, default="")       # frase que compoe o "Resumo do Servico"
    ativo = Column(Boolean, nullable=False, default=True)


class Manutencao(Base):
    """Uma por OS — espelha a unicidade (os, tipo) de os_certificados.

    Dentro dela cabem varios servicos: um mesmo relatorio cobre, por exemplo,
    troca de pilha interna E troca do Bluetooth.
    """
    __tablename__ = "manutencoes"
    __table_args__ = (UniqueConstraint("os", name="uq_manutencoes_os"),)

    id = Column(Integer, primary_key=True, index=True)
    os = Column(Integer, ForeignKey("ordens.id", ondelete="CASCADE"), nullable=False, index=True)
    numero = Column(String(50), nullable=True)          # digitado; serie propria do laboratorio
    data_manutencao = Column(Date, nullable=True)
    resumo = Column(Text, nullable=True)                # texto FINAL, nao a receita
    criado_por = Column(String(255), nullable=True)
    criado_em = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    atualizado_em = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    itens = relationship("ManutencaoItem", cascade="all, delete-orphan",
                         order_by="ManutencaoItem.ordem", lazy="selectin")


class ManutencaoItem(Base):
    __tablename__ = "manutencao_itens"
    __table_args__ = (UniqueConstraint("manutencao", "servico", name="uq_manutencao_itens_servico"),)

    id = Column(Integer, primary_key=True, index=True)
    manutencao = Column(Integer, ForeignKey("manutencoes.id", ondelete="CASCADE"), nullable=False, index=True)
    servico = Column(Integer, ForeignKey("manutencao_servicos.id"), nullable=False)
    ordem = Column(Integer, nullable=False, default=0)   # posicao escolhida; define a ordem no texto

    servico_rel = relationship("ManutencaoServico", lazy="joined")
