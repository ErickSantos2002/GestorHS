from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.models.database import Base


class CertificadoAvulso(Base):
    """Certificado emitido SEM OS, cliente ou aparelho cadastrados (aparelhos de POC).

    Nao ha FK para clientes nem equipamentos_cliente — e exatamente o ponto da feature.
    O `html` e auto-contido; os campos soltos existem so para a listagem.
    """
    __tablename__ = "certificados_avulsos"

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String(1), nullable=False)          # C / M — do template escolhido
    html = Column(Text, nullable=False)               # certificado ja preenchido
    nomecli = Column(String(200), nullable=True)
    serie = Column(String(50), nullable=True)
    calib_cert = Column(String(50), nullable=True)
    data_calibracao = Column(Date, nullable=True)
    usuario = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    data_geracao = Column(DateTime(timezone=True), nullable=True)

    usuario_rel = relationship("Usuario", lazy="joined")

    @property
    def usuario_nome(self):
        return self.usuario_rel.nome if self.usuario_rel else None
