from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, UniqueConstraint
from app.models.database import Base


class OSCertificado(Base):
    __tablename__ = "os_certificados"
    __table_args__ = (UniqueConstraint("os", "tipo", name="uq_os_certificados_os_tipo"),)

    id = Column(Integer, primary_key=True, index=True)
    os = Column(Integer, ForeignKey("ordens.id"), nullable=False)
    tipo = Column(String(1), nullable=False)  # C / M
    html = Column(Text, nullable=True)
    pdf = Column(String(50), nullable=True)
    data_geracao = Column(DateTime(timezone=True), nullable=True)
