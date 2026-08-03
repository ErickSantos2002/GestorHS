from sqlalchemy import Boolean, Column, Date, Integer, Numeric, String

from app.models.database import Base


class CertificadoPadrao(Base):
    """Cilindro de gas padrao usado na calibracao, com vigencia.

    A OS grava qual cilindro foi usado (ordens.padrao_id), para que regerar um
    certificado antigo mantenha a rastreabilidade correta em vez de apontar para
    o cilindro que estiver em uso hoje.
    """
    __tablename__ = "certificado_padrao"

    id = Column(Integer, primary_key=True, index=True)
    numero_cilindro = Column(String(50), nullable=False)
    numero_certificado = Column(String(50), nullable=True)
    concentracao = Column(Numeric(10, 4), nullable=True)
    incerteza_concentracao = Column(Numeric(10, 4), nullable=True)
    unidade = Column(String(20), nullable=True, default="µmol/mol")
    vigencia_inicio = Column(Date, nullable=True)
    vigencia_fim = Column(Date, nullable=True)   # nulo = ainda vigente
    ativo = Column(Boolean, nullable=False, default=True)
