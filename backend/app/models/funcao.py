from sqlalchemy import Column, Integer, String
from app.models.database import Base


class Funcao(Base):
    __tablename__ = "funcoes"

    id = Column(Integer, primary_key=True, index=True)
    descricao = Column(String(100), nullable=False, unique=True)
