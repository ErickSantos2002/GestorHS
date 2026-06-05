from sqlalchemy import Column, Integer, String, Date
from sqlalchemy.orm import relationship
from app.models.database import Base


class Caixa(Base):
    __tablename__ = "caixas"

    id = Column(Integer, primary_key=True, index=True)
    data = Column(Date, nullable=True)
    status = Column(String(1), nullable=False, default="P")  # P=Pendente, A=Aberta, F=Finalizada
    obs = Column(String(1000), nullable=True)

    ordens = relationship("Ordem", back_populates="caixa_rel", lazy="selectin")

    @property
    def total_os(self) -> int:
        return len(self.ordens)

    @property
    def clientes(self) -> list[str]:
        nomes = {o.cliente_nome for o in self.ordens if o.cliente_nome}
        return sorted(nomes)
