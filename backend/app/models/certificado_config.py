from sqlalchemy import Column, Integer, Numeric, String, Text

from app.models.database import Base


class CertificadoConfig(Base):
    """Parametros globais do certificado de calibracao — linha UNICA (singleton).

    Os defaults sao os valores da planilha EPS-LAB-002 enviada pela Qualidade.
    Ficam aqui, no modelo, e nao so na migracao, porque os testes criam o schema
    com Base.metadata.create_all — a migracao nao roda neles.
    """
    __tablename__ = "certificado_config"

    id = Column(Integer, primary_key=True, index=True)
    # parametros do calculo
    valor_referencia = Column(Numeric(10, 4), nullable=True, default=0.1)
    limite_minimo = Column(Numeric(10, 4), nullable=True, default=0.15)
    limite_maximo = Column(Numeric(10, 4), nullable=True, default=0.19)
    resolucao_instrumento = Column(Numeric(10, 4), nullable=True, default=0.1)
    incerteza_padrao_temp = Column(Numeric(10, 4), nullable=True, default=0.052)
    resolucao_pressao = Column(Numeric(10, 4), nullable=True)
    incerteza_padrao_pressao = Column(Numeric(10, 4), nullable=True)
    fator_k = Column(Numeric(4, 2), nullable=True, default=2)
    # identidade do laboratorio
    tecnico_nome = Column(String(100), nullable=True, default="Walbert Santos")
    tecnico_cargo = Column(String(100), nullable=True, default="Técnico em Metrologia")
    equipamentos_auxiliares = Column(Text, nullable=True)
    margem_temperatura = Column(String(50), nullable=True, default="20 ºC ~ 24 ºC")
