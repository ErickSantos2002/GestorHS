from sqlalchemy import Column, Integer, BigInteger, String, Text, Boolean, ForeignKey, Date
from app.models.database import Base


class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    grupo = Column(Integer, ForeignKey("grupos.id"), nullable=True)
    nome = Column(String(100), nullable=True)
    cgc = Column(String(14), nullable=True)
    cpf = Column(String(11), nullable=True)
    endereco = Column(String(100), nullable=True)
    numero = Column(BigInteger, nullable=True)
    complemento = Column(String(60), nullable=True)
    bairro = Column(String(100), nullable=True)
    municipio = Column(String(100), nullable=True)
    estado = Column(String(2), nullable=True)
    cep = Column(String(8), nullable=True)
    contato = Column(String(30), nullable=True)
    email = Column(String(100), nullable=True)
    telefones = Column(String(250), nullable=True)
    celular = Column(String(250), nullable=True)
    whatsapp = Column(String(50), nullable=True)
    whatsapp1 = Column(String(50), nullable=True)
    whatsapp2 = Column(String(50), nullable=True)
    insc_mun = Column(String(20), nullable=True)
    insc_est = Column(String(20), nullable=True)
    datcad = Column(Date, nullable=True)
    obs = Column(Text, nullable=True)
    imagem = Column(String(50), nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
