from sqlalchemy import (Column, Integer, String, Text, Date, DateTime,
                        ForeignKey, UniqueConstraint)
from sqlalchemy.orm import relationship

from app.models.database import Base


class CertificadoVenda(Base):
    """Primeiro certificado do aparelho, emitido na VENDA — sem OS.

    Diferente de CertificadoAvulso (sem vinculo nenhum, para aparelho de POC), este e
    ancorado no aparelho da frota do cliente. O unique em equipamento_cliente garante
    "um por aparelho" no banco: regerar e um upsert, nao uma duplicata.

    Nao ha coluna `tipo`: certificado de venda e sempre de calibracao ("C").
    """
    __tablename__ = "certificados_venda"
    __table_args__ = (
        UniqueConstraint("equipamento_cliente", name="uq_certificados_venda_equip"),
    )

    id = Column(Integer, primary_key=True, index=True)
    equipamento_cliente = Column(Integer, ForeignKey("equipamentos_cliente.id"), nullable=False)
    html = Column(Text, nullable=False)               # certificado preenchido, auto-contido
    calib_cert = Column(String(50), nullable=True)    # so para a listagem
    data_calibracao = Column(Date, nullable=True)     # so para a listagem
    usuario = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    data_geracao = Column(DateTime(timezone=True), nullable=True)

    usuario_rel = relationship("Usuario", lazy="joined")

    @property
    def usuario_nome(self):
        return self.usuario_rel.nome if self.usuario_rel else None
