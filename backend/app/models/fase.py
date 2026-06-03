from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.models.database import Base


class Fase(Base):
    __tablename__ = "fases"

    id = Column(Integer, primary_key=True, index=True)
    descricao = Column(String(100), nullable=False)
    cor = Column(String(6), nullable=False, default="000000")
    funcao_responsavel = Column(Integer, ForeignKey("funcoes.id"), nullable=True)

    funcao_rel = relationship("Funcao", lazy="joined")

    @property
    def funcao_nome(self):
        return self.funcao_rel.descricao if self.funcao_rel else None
