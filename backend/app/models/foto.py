from sqlalchemy import Column, Integer, String, ForeignKey
from app.models.database import Base


class Foto(Base):
    __tablename__ = "fotos"

    id = Column(Integer, primary_key=True, index=True)
    cliente = Column(Integer, ForeignKey("clientes.id"), nullable=True)
    codigo = Column(Integer, nullable=True)
    cor = Column(Integer, nullable=True, default=0)
    tipo = Column(String(1), nullable=True, default="I")
    posicao = Column(Integer, nullable=True, default=1)
    arquivo = Column(String(50), nullable=True)
    legenda = Column(String(250), nullable=True)
    os = Column(Integer, ForeignKey("ordens.id"), nullable=True)
