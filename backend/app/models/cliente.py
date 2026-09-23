from sqlalchemy import Column, Integer, BigInteger, String, Text, Boolean, ForeignKey, Date, DateTime
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
    # Espelhamento no Tiny ERP (0032). So o Cliente destinatario de proposta e'
    # espelhado, e so criado/adotado — nunca alterado. Ver integrations/tiny_client.py.
    tiny_id = Column(Integer, nullable=True, index=True)      # id do contato no Tiny
    tiny_status = Column(String(10), nullable=True)           # pendente | enviada | erro
    tiny_erro = Column(String(255), nullable=True)            # ultima recusa, para a tela
    tiny_em = Column(DateTime(timezone=True), nullable=True)  # ultima tentativa
