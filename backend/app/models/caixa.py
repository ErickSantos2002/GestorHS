from sqlalchemy import Column, Integer, String, Date, ForeignKey
from sqlalchemy.orm import relationship
from app.models.database import Base


class Caixa(Base):
    __tablename__ = "caixas"

    id = Column(Integer, primary_key=True, index=True)
    data = Column(Date, nullable=True)
    obs = Column(String(1000), nullable=True)
    fase = Column(Integer, ForeignKey("fases.id"), nullable=True)

    ordens = relationship("Ordem", back_populates="caixa_rel", lazy="selectin")
    fase_rel = relationship("Fase", lazy="joined")

    @property
    def total_os(self) -> int:
        return len(self.ordens)

    @property
    def clientes(self) -> list[str]:
        nomes = {o.cliente_nome for o in self.ordens if o.cliente_nome}
        return sorted(nomes)

    @property
    def fase_descricao(self):
        return self.fase_rel.descricao if self.fase_rel else None

    @property
    def fase_cor(self):
        return self.fase_rel.cor if self.fase_rel else None
