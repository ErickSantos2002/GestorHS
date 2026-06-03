from sqlalchemy import Column, Integer, String
from app.models.database import Base


class Marca(Base):
    __tablename__ = "marcas"

    id = Column(Integer, primary_key=True, index=True)
    descricao = Column(String(100), nullable=False)
    imagem = Column(String(50), nullable=True)
