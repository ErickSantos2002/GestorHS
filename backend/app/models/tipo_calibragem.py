from sqlalchemy import Column, Integer, String, Text, Numeric
from app.models.database import Base


class TipoCalibragem(Base):
    __tablename__ = "tipos_calibragem"

    id = Column(Integer, primary_key=True, index=True)
    descricao = Column(String(200), nullable=False)
    texto = Column(Text, nullable=True)
    valor = Column(Numeric(10, 2), nullable=False, default=0)
