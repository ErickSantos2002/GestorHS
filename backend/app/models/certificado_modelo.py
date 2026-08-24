from sqlalchemy import Column, Integer, String, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.database import Base


class CertificadoModelo(Base):
    __tablename__ = "certificados"
    __table_args__ = (UniqueConstraint("equipamento", "tipo", name="uq_certificados_equipamento_tipo"),)

    id = Column(Integer, primary_key=True, index=True)
    # Nulo = modelo GENERICO. Hoje so o tipo M usa esse caminho (ver modelo_para
    # em core/certificado_gerar.py); existe tambem um registro legado tipo C.
    equipamento = Column(Integer, ForeignKey("equipamentos.id"), nullable=True)
    tipo = Column(String(1), nullable=False, default="C")  # C=Calibração, M=Manutenção
    descricao = Column(String(100), nullable=True)
    texto = Column(Text, nullable=True)

    equipamento_rel = relationship("Equipamento", lazy="joined")

    @property
    def equipamento_descricao(self):
        return self.equipamento_rel.descricao if self.equipamento_rel else None
