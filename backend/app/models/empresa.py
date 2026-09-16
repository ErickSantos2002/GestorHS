from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.models.database import Base


class Empresa(Base):
    """Filial: so dados cadastrais, sem frota. Os aparelhos vem da matriz
    (`cliente`), que e' opcional. Documento unico somando `clientes` e
    `empresas` — a checagem cruzada vive em core/empresa_servico.py."""
    __tablename__ = "empresas"
    __table_args__ = (
        CheckConstraint("(cgc IS NULL) <> (cpf IS NULL)", name="ck_empresas_um_documento"),
    )

    id = Column(Integer, primary_key=True, index=True)
    cliente = Column(Integer, ForeignKey("clientes.id", ondelete="SET NULL"), nullable=True, index=True)
    nome = Column(String(100), nullable=False)
    cgc = Column(String(14), nullable=True, unique=True)
    cpf = Column(String(11), nullable=True, unique=True)
    endereco = Column(String(100), nullable=True)
    numero = Column(String(20), nullable=True)
    complemento = Column(String(60), nullable=True)
    bairro = Column(String(100), nullable=True)
    municipio = Column(String(100), nullable=True)
    estado = Column(String(2), nullable=True)
    cep = Column(String(8), nullable=True)
    email = Column(String(100), nullable=True)
    telefone = Column(String(50), nullable=True)
    insc_est = Column(String(20), nullable=True)
    ativo = Column(Boolean, nullable=False, default=True, server_default=sa.text("true"))
    # Estado do espelhamento no Tiny ERP. Nulo = nunca entrou na fila (integracao
    # desligada ou cadastro anterior a ela). Ver core/tiny.py e integrations/tiny_client.py.
    tiny_id = Column(Integer, nullable=True, index=True)      # id do contato no Tiny
    tiny_status = Column(String(10), nullable=True)           # pendente | enviada | erro
    tiny_erro = Column(String(255), nullable=True)            # ultima recusa, para a tela
    tiny_em = Column(DateTime(timezone=True), nullable=True)  # ultima tentativa
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    matriz_rel = relationship("Cliente", lazy="joined")
