from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from app.models.database import Base


class LogOS(Base):
    __tablename__ = "logs_os"

    id = Column(Integer, primary_key=True, index=True)
    os = Column(Integer, ForeignKey("ordens.id"), nullable=False)
    usuario = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    datalog = Column(DateTime(timezone=True), nullable=True)
    autor = Column(String(1), nullable=False, default="1")
    texto = Column(Text, nullable=True)
