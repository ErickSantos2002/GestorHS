from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, ForeignKey, JSON, DateTime
from sqlalchemy.orm import relationship
from app.models.database import Base


class PropostaVersao(Base):
    __tablename__ = "proposta_versoes"
    id = Column(Integer, primary_key=True, index=True)
    proposta = Column(Integer, ForeignKey("propostas.id", ondelete="CASCADE"), nullable=False, index=True)
    numero_versao = Column(Integer, nullable=False)
    snapshot = Column(JSON, nullable=True)
    pdf_path = Column(String(500), nullable=True)
    alterado_por = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    proposta_rel = relationship("Proposta", back_populates="versoes")
