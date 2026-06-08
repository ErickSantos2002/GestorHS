from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.models.database import Base


class CertificadoModelo(Base):
    __tablename__ = "certificados"

    id = Column(Integer, primary_key=True, index=True)
    equipamento = Column(Integer, ForeignKey("equipamentos.id"), nullable=False, unique=True)
    descricao = Column(String(100), nullable=True)
    texto = Column(Text, nullable=True)

    equipamento_rel = relationship("Equipamento", lazy="joined")

    @property
    def equipamento_descricao(self):
        return self.equipamento_rel.descricao if self.equipamento_rel else None
