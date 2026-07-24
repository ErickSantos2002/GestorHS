from sqlalchemy import Column, Integer, String, Text, Numeric, Boolean
from app.models.database import Base


class Servico(Base):
    __tablename__ = "servicos"
    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(100), nullable=True, unique=True, index=True)
    nome = Column(String(255), nullable=False, index=True)
    descricao = Column(Text, nullable=True)
    unidade = Column(String(20), nullable=True)
    preco = Column(Numeric(12, 2), nullable=False, default=0)
    codigo_servico = Column(String(100), nullable=True)  # CNAE / codigo de servico
    ativo = Column(Boolean, nullable=False, default=True)
