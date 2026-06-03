from sqlalchemy import Column, Integer, String, ForeignKey
from app.models.database import Base


class Categoria(Base):
    __tablename__ = "categorias"

    id = Column(Integer, primary_key=True, index=True)
    setor = Column(Integer, ForeignKey("setores.id"), nullable=True)
    posicao = Column(Integer, nullable=False, default=0)
    descricao = Column(String(200), nullable=True)
