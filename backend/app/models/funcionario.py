from sqlalchemy import Column, Integer, BigInteger, String, Boolean, ForeignKey, Date
from app.models.database import Base


class Funcionario(Base):
    __tablename__ = "funcionarios"

    id = Column(Integer, primary_key=True, index=True)
    cliente = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    setor = Column(Integer, ForeignKey("setores.id"), nullable=True)
    matricula = Column(String(50), nullable=False, default="0")
    centro = Column(String(50), nullable=True)
    nome = Column(String(100), nullable=True)
    email = Column(String(200), nullable=True)
    cargo = Column(String(50), nullable=True)
    admissao = Column(Date, nullable=True)
    idade = Column(Integer, nullable=True)
    sexo = Column(String(1), nullable=True)
    estado = Column(String(2), nullable=True, default="SP")
    cidade = Column(String(100), nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
