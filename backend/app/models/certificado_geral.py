from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.models.database import Base


class CertificadoGeral(Base):
    """Documento PDF avulso (ex.: certificado de gas anual), sem vinculo com OS/cliente.

    Servido ao publico so por link HMAC assinado (certgeral:{id})."""
    __tablename__ = "certificados_gerais"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(200), nullable=False)
    arquivo = Column(String(64), nullable=False)   # basename do PDF no storage
    usuario = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    data_upload = Column(DateTime(timezone=True), nullable=True)

    usuario_rel = relationship("Usuario", lazy="joined")

    @property
    def usuario_nome(self):
        return self.usuario_rel.nome if self.usuario_rel else None
