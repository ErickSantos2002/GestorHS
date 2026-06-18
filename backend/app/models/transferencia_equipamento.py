from sqlalchemy import Column, Integer, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from app.models.database import Base


class TransferenciaEquipamento(Base):
    __tablename__ = "transferencias_equipamento"

    id = Column(Integer, primary_key=True, index=True)
    equipamento_cliente = Column(Integer, ForeignKey("equipamentos_cliente.id"), nullable=False)
    de_cliente = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    para_cliente = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    data = Column(DateTime(timezone=True), nullable=False)
    usuario = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    obs = Column(Text, nullable=True)

    de_rel = relationship("Cliente", foreign_keys=[de_cliente], lazy="joined")
    para_rel = relationship("Cliente", foreign_keys=[para_cliente], lazy="joined")
    usuario_rel = relationship("Usuario", lazy="joined")

    @property
    def de_cliente_nome(self):
        return self.de_rel.nome if self.de_rel else None

    @property
    def para_cliente_nome(self):
        return self.para_rel.nome if self.para_rel else None

    @property
    def usuario_nome(self):
        return self.usuario_rel.nome if self.usuario_rel else None
