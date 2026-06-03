from sqlalchemy import Column, Integer, ForeignKey, Date
from app.models.database import Base


class HistoricoEquipamento(Base):
    __tablename__ = "historico_equipamentos"

    id = Column(Integer, primary_key=True, index=True)
    equipamento_cliente = Column(Integer, ForeignKey("equipamentos_cliente.id"), nullable=False)
    datamov = Column(Date, nullable=True)
    saida = Column(Integer, nullable=True)
    entrada = Column(Integer, nullable=True)
