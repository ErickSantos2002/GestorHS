from sqlalchemy import Column, Integer, String, Text
from app.models.database import Base


class Grupo(Base):
    __tablename__ = "grupos"

    id = Column(Integer, primary_key=True, index=True)
    descricao = Column(String(200), nullable=False)
    texto = Column(Text, nullable=True)
