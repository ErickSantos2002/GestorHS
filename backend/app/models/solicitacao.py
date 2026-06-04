from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.models.database import Base


class Solicitacao(Base):
    __tablename__ = "solicitacoes"

    id = Column(Integer, primary_key=True, index=True)
    cliente = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    equipamento_cliente = Column(Integer, ForeignKey("equipamentos_cliente.id"), nullable=False)
    status = Column(String(20), nullable=False, default="pendente")
    data_solicitacao = Column(DateTime(timezone=True), nullable=True)
    data_atendimento = Column(DateTime(timezone=True), nullable=True)
    atendido_por = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    obs = Column(Text, nullable=True)

    cliente_rel = relationship("Cliente", lazy="joined")
    equipamento_rel = relationship("EquipamentoCliente", lazy="joined")
    atendente_rel = relationship("Usuario", lazy="joined")

    @property
    def cliente_nome(self):
        return self.cliente_rel.nome if self.cliente_rel else None

    @property
    def equipamento_descricao(self):
        return self.equipamento_rel.equipamento_descricao if self.equipamento_rel else None

    @property
    def atendido_por_nome(self):
        return self.atendente_rel.nome if self.atendente_rel else None
