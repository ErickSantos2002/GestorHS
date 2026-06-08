from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime, Numeric
from sqlalchemy.orm import relationship
from app.models.database import Base


class Ordem(Base):
    __tablename__ = "ordens"

    id = Column(Integer, primary_key=True, index=True)
    cliente = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    equipamento_cliente = Column(Integer, ForeignKey("equipamentos_cliente.id"), nullable=True)
    fase = Column(Integer, ForeignKey("fases.id"), nullable=True)
    tipo_calibragem = Column(Integer, nullable=True)
    caixa = Column(Integer, ForeignKey("caixas.id"), nullable=True)
    checklist = Column(String(50), nullable=True)
    # datas do ciclo
    data_solicitacao = Column(DateTime(timezone=True), nullable=True)
    data_envio = Column(DateTime(timezone=True), nullable=True)
    data_chegada = Column(DateTime(timezone=True), nullable=True)
    data_calibracao = Column(DateTime(timezone=True), nullable=True)
    data_retorno = Column(DateTime(timezone=True), nullable=True)
    data_entrega = Column(DateTime(timezone=True), nullable=True)
    prox_calibragem = Column(DateTime(timezone=True), nullable=True)
    # rastreio
    cod_envio = Column(String(50), nullable=True)
    cod_retorno = Column(String(50), nullable=True)
    etiqueta = Column(String(50), nullable=True)
    # resultados (preenchidos na 3E — intocados aqui)
    calib_cert = Column(String(50), nullable=True)
    calib_temp = Column(String(50), nullable=True)
    calib_pressao = Column(String(50), nullable=True)
    calib_teste1 = Column(String(50), nullable=True)
    calib_teste2 = Column(String(50), nullable=True)
    calib_teste3 = Column(String(50), nullable=True)
    calib_teste_media = Column(String(50), nullable=True)
    calib_situacao = Column(String(50), nullable=True)
    pdf_certificado = Column(String(50), nullable=True)
    certificado = Column(Text, nullable=True)
    # financeiro (fora do v1)
    valor = Column(Numeric(10, 2), nullable=False, default=0)
    frete_envio = Column(Numeric(10, 2), nullable=False, default=0)
    frete_retorno = Column(Numeric(10, 2), nullable=False, default=0)
    pago = Column(Boolean, nullable=False, default=False)
    recebido = Column(Boolean, nullable=False, default=False)
    # controle
    garantia = Column(Boolean, nullable=False, default=True)
    situacao = Column(String(1), nullable=False, default="E")
    chave = Column(String(12), nullable=True)
    pilhas = Column(Integer, nullable=True, default=0)
    sopradores = Column(Integer, nullable=True, default=0)
    arquivo = Column(String(50), nullable=True)
    obs = Column(Text, nullable=True)
    # adicionadas em 0002
    tipo_servico = Column(String(1), nullable=True)
    condicao_chegada = Column(Text, nullable=True)
    acessorios = Column(Text, nullable=True)
    aceite = Column(Boolean, nullable=False, default=False)
    data_aceite = Column(DateTime(timezone=True), nullable=True)

    cliente_rel = relationship("Cliente", lazy="joined")
    equipamento_rel = relationship("EquipamentoCliente", lazy="joined")
    fase_rel = relationship("Fase", lazy="joined")
    caixa_rel = relationship("Caixa", back_populates="ordens", lazy="joined")

    @property
    def cliente_nome(self):
        return self.cliente_rel.nome if self.cliente_rel else None

    @property
    def equipamento_serie(self):
        return self.equipamento_rel.serie if self.equipamento_rel else None

    @property
    def equipamento_descricao(self):
        return self.equipamento_rel.equipamento_descricao if self.equipamento_rel else None

    @property
    def fase_descricao(self):
        return self.fase_rel.descricao if self.fase_rel else None

    @property
    def fase_cor(self):
        return self.fase_rel.cor if self.fase_rel else None

    @property
    def caixa_obs(self):
        return self.caixa_rel.obs if self.caixa_rel else None

    @property
    def checklist_ids(self):
        from app.core.recebimento import checklist_csv_para_ids
        return checklist_csv_para_ids(self.checklist)

    @property
    def acessorios_presentes(self):
        from app.core.recebimento import CHECKLIST_ACESSORIOS
        return [CHECKLIST_ACESSORIOS[i] for i in self.checklist_ids]

    @property
    def bocais(self):
        return self.sopradores or 0
