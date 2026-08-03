from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CertificadoConfigIn(BaseModel):
    valor_referencia: Decimal | None = None
    limite_minimo: Decimal | None = None
    limite_maximo: Decimal | None = None
    resolucao_instrumento: Decimal | None = None
    incerteza_padrao_temp: Decimal | None = None
    resolucao_pressao: Decimal | None = None
    incerteza_padrao_pressao: Decimal | None = None
    fator_k: Decimal | None = None
    tecnico_nome: str | None = None
    tecnico_cargo: str | None = None
    equipamentos_auxiliares: str | None = None
    margem_temperatura: str | None = None


class CertificadoConfigOut(CertificadoConfigIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class CertificadoPadraoIn(BaseModel):
    numero_cilindro: str = Field(min_length=1)
    numero_certificado: str | None = None
    concentracao: Decimal | None = None
    incerteza_concentracao: Decimal | None = None
    unidade: str | None = "µmol/mol"
    vigencia_inicio: date | None = None
    vigencia_fim: date | None = None
    ativo: bool = True


class CertificadoPadraoUpdate(BaseModel):
    numero_cilindro: str | None = None
    numero_certificado: str | None = None
    concentracao: Decimal | None = None
    incerteza_concentracao: Decimal | None = None
    unidade: str | None = None
    vigencia_inicio: date | None = None
    vigencia_fim: date | None = None
    ativo: bool | None = None


class CertificadoPadraoOut(CertificadoPadraoIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class CalculoPreviaIn(BaseModel):
    medicoes: list[str | None] = Field(default_factory=list)


class CalculoPreviaOut(BaseModel):
    """Tudo em texto ja formatado em PT-BR: a tela apenas exibe, nao recalcula nada."""
    erros: list[str]
    media: str
    desvio_padrao: str
    incerteza_combinada: str
    incerteza_expandida: str
    fator_k: str
    limite_minimo: str
    limite_maximo: str
    fora_da_faixa: list[bool]
