from sqlalchemy import Column, Integer, String
from app.models.database import Base


class Setor(Base):
    __tablename__ = "setores"

    id = Column(Integer, primary_key=True, index=True)
    descricao = Column(String(200), nullable=False)
