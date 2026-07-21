from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, func

from app.models.database import Base


class LogIntegracao(Base):
    """Um evento de integracao de saida (TaskHS/GrowthHS): sucesso, erro ou pulado.

    Guarda o payload enviado para permitir o reenvio (re-post do mesmo payload).
    Escrito best-effort pelo writer em app/integrations/log_integracao.py.
    """
    __tablename__ = "logs_integracao"

    id = Column(Integer, primary_key=True, index=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    integracao = Column(String(20), nullable=False)      # taskhs | growthhs
    tipo = Column(String(30), nullable=False)            # os_card | os_espelho | vencendo | atrasados | desconhecido
    external_id = Column(String(100), nullable=True)
    referencia_os = Column(Integer, nullable=True, index=True)
    status = Column(String(20), nullable=False)          # sucesso | erro | pulado
    motivo = Column(String(50), nullable=True)           # desligado | sem_equipamento | ...
    http_status = Column(Integer, nullable=True)
    resposta = Column(Text, nullable=True)               # corpo/erro truncado
    payload = Column(JSON, nullable=True)                # payload enviado (base do reenvio)
