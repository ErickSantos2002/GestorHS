from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, Numeric, Date
from app.models.database import Base


class Equipamento(Base):
    __tablename__ = "equipamentos"

    id = Column(Integer, primary_key=True, index=True)
    categoria = Column(Integer, ForeignKey("categorias.id"), nullable=True)
    marca = Column(Integer, ForeignKey("marcas.id"), nullable=True)
    descricao = Column(String(100), nullable=True)
    detalhes = Column(Text, nullable=True)
    especificacao = Column(Text, nullable=True)
    preco_cod = Column(Numeric(10, 2), nullable=False, default=0)
    preco_por = Column(Numeric(10, 2), nullable=False, default=0)
    custo = Column(Numeric(10, 2), nullable=False, default=0)
    peso_calibragem = Column(Numeric(10, 3), nullable=False, default=0)
    peso = Column(Numeric(10, 3), nullable=False, default=0)
    imagem = Column(String(50), nullable=True)
    estoque = Column(Integer, nullable=False, default=0)
    estoque_min = Column(Integer, nullable=False, default=0)
    ativo = Column(Boolean, nullable=False, default=False)
    destaque = Column(Boolean, nullable=False, default=False)
    datacad = Column(Date, nullable=True)
