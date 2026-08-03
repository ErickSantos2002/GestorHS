from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


def _numero_ptbr(valor):
    """Aceita o numero no MESMO formato que a tela exibe: virgula decimal, e campo
    vazio como ausencia de valor.

    O sistema inteiro imprime numero em pt-BR — `formatar_numero` devolve "0,1301" —
    entao o laboratorio digita virgula. Recusar isso com 422 seria culpar o usuario
    por seguir o formato do proprio app. E o formulario manda '' no campo que ficou
    em branco, nao null: '' nao e Decimal valido, mas significa "nao informado".
    """
    if isinstance(valor, str):
        texto = valor.strip().replace(",", ".")
        return texto or None
    return valor


def _data_opcional(valor):
    """Campo de data em branco chega como '' do formulario — trata como ausente."""
    if isinstance(valor, str) and not valor.strip():
        return None
    return valor


# Decimal e date que aceitam o que o formulario realmente manda.
NumeroPtBr = Annotated[Decimal | None, BeforeValidator(_numero_ptbr)]
DataOpcional = Annotated[date | None, BeforeValidator(_data_opcional)]


class CertificadoConfigIn(BaseModel):
    valor_referencia: NumeroPtBr = None
    limite_minimo: NumeroPtBr = None
    limite_maximo: NumeroPtBr = None
    resolucao_instrumento: NumeroPtBr = None
    incerteza_padrao_temp: NumeroPtBr = None
    resolucao_pressao: NumeroPtBr = None
    incerteza_padrao_pressao: NumeroPtBr = None
    fator_k: NumeroPtBr = None
    tecnico_nome: str | None = None
    tecnico_cargo: str | None = None
    equipamentos_auxiliares: str | None = None
    margem_temperatura: str | None = None
    doc_gas_id: int | None = None
    doc_termohigrometro_id: int | None = None
    doc_barometro_id: int | None = None


class CertificadoConfigOut(CertificadoConfigIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class CertificadoPadraoIn(BaseModel):
    numero_cilindro: str = Field(min_length=1)
    numero_certificado: str | None = None
    concentracao: NumeroPtBr = None
    incerteza_concentracao: NumeroPtBr = None
    unidade: str | None = "µmol/mol"
    vigencia_inicio: DataOpcional = None
    vigencia_fim: DataOpcional = None
    ativo: bool = True


class CertificadoPadraoUpdate(BaseModel):
    numero_cilindro: str | None = None
    numero_certificado: str | None = None
    concentracao: NumeroPtBr = None
    incerteza_concentracao: NumeroPtBr = None
    unidade: str | None = None
    vigencia_inicio: DataOpcional = None
    vigencia_fim: DataOpcional = None
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
