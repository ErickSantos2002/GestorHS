from datetime import date
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Date, DateTime
from sqlalchemy.orm import relationship

from app.models.database import Base
from app.core.calibracao import status_calibracao as _calc_status


class EquipamentoCliente(Base):
    __tablename__ = "equipamentos_cliente"

    id = Column(Integer, primary_key=True, index=True)
    cliente = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    equipamento = Column(Integer, ForeignKey("equipamentos.id"), nullable=False)
    modulo = Column(Integer, nullable=False, default=0)
    serie = Column(String(50), nullable=True)
    patrimonio = Column(String(50), nullable=True)
    datacompra = Column(Date, nullable=True)
    ult_calibragem = Column(Date, nullable=True)
    prox_calibragem = Column(Date, nullable=True)
    ult_aviso = Column(DateTime(timezone=True), nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
    status = Column(String(1), nullable=False, default="A")
    os_atual = Column(Integer, nullable=True)
    calib_cert = Column(String(50), nullable=True)
    calib_temp = Column(String(50), nullable=True)
    calib_pressao = Column(String(50), nullable=True)
    calib_teste1 = Column(String(50), nullable=True)
    calib_teste2 = Column(String(50), nullable=True)
    calib_teste3 = Column(String(50), nullable=True)
    calib_teste4 = Column(String(50), nullable=True)
    calib_teste5 = Column(String(50), nullable=True)
    calib_teste_media = Column(String(50), nullable=True)
    calib_situacao = Column(String(50), nullable=True)

    cliente_rel = relationship("Cliente", lazy="joined")
    equipamento_rel = relationship("Equipamento", lazy="joined")

    @property
    def status_calibracao(self) -> str:
        return _calc_status(self.prox_calibragem, date.today())

    @property
    def cliente_nome(self):
        return self.cliente_rel.nome if self.cliente_rel else None

    @property
    def equipamento_descricao(self):
        return self.equipamento_rel.descricao if self.equipamento_rel else None
