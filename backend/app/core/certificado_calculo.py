"""Matematica do certificado de calibracao — espelha a aba BASE DE CALCULO da
planilha da Qualidade (docs/Certificado Iblow.xlsx).

Modulo PURO: sem Session, sem I/O, sem import de app.models. E o que permite
testar as formulas contra a planilha isoladamente.
"""
import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

# Divisor da distribuicao retangular usado em cada componente de incerteza
# (na planilha, o /SQRT(3) das celulas C10:C13).
_RAIZ_3 = math.sqrt(3)


@dataclass(frozen=True)
class ParametrosCalculo:
    """Os valores da aba Configuracoes que entram no calculo."""
    valor_referencia: float | None
    resolucao_instrumento: float | None
    incerteza_padrao_temp: float | None
    resolucao_pressao: float | None
    incerteza_padrao_pressao: float | None
    fator_k: float


@dataclass(frozen=True)
class ResultadoCalculo:
    medicoes: list[float]            # so as medicoes validas
    erros: list[float | None]        # alinhado com a ENTRADA: None onde estava em branco
    media: float | None
    desvio_padrao: float
    incerteza_combinada: float
    incerteza_expandida: float
    fator_k: float


def _para_float(valor: str | float | None) -> float | None:
    """Texto do formulario -> float. Aceita virgula decimal. Branco/lixo -> None."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip().replace(",", ".")
    if not texto:
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def componente_retangular(valor: float | None) -> float:
    """Componente de incerteza tipo B, distribuicao retangular: valor / sqrt(3).

    Componente ausente contribui ZERO, nao erro — B12/B13 estao vazias na planilha
    e entram como zero na SUMSQ.
    """
    if valor is None:
        return 0.0
    return valor / _RAIZ_3


def desvio_padrao_amostral(medicoes: Sequence[float]) -> float:
    """Desvio padrao AMOSTRAL (n-1) — e o que a funcao STDEV do Excel calcula.

    Com pstdev (populacional) os numeros da planilha nao batem. Com menos de duas
    medicoes retorna 0, em vez de estourar como statistics.stdev faria — o Excel
    tambem trata celula vazia como zero aqui.
    """
    if len(medicoes) < 2:
        return 0.0
    return statistics.stdev(medicoes)


def calcular(medicoes_texto: Sequence[str | None], parametros: ParametrosCalculo) -> ResultadoCalculo:
    valores = [_para_float(m) for m in medicoes_texto]
    medicoes = [v for v in valores if v is not None]

    ref = parametros.valor_referencia
    erros: list[float | None] = [
        None if (v is None or ref is None) else v - ref for v in valores
    ]

    media = statistics.fmean(medicoes) if medicoes else None
    desvio = desvio_padrao_amostral(medicoes)

    componentes = [
        componente_retangular(parametros.resolucao_instrumento),
        componente_retangular(parametros.incerteza_padrao_temp),
        componente_retangular(parametros.resolucao_pressao),
        componente_retangular(parametros.incerteza_padrao_pressao),
    ]
    # uc = sqrt(u_medicao^2 + SUMSQ(componentes))  — celula B15 da planilha
    uc = math.sqrt(desvio**2 + sum(c**2 for c in componentes))
    # U = uc * k  — celula B16
    expandida = uc * parametros.fator_k

    return ResultadoCalculo(
        medicoes=medicoes,
        erros=erros,
        media=media,
        desvio_padrao=desvio,
        incerteza_combinada=uc,
        incerteza_expandida=expandida,
        fator_k=parametros.fator_k,
    )


def formatar_numero(valor: float | None, casas: int = 4) -> str:
    """Numero -> texto do certificado, em PT-BR, sem zeros inuteis a direita.

    ULTIMO passo do pipeline: o calculo roda com precisao cheia e so aqui arredonda.
    Arredondar no meio muda o U na terceira casa.
    """
    if valor is None:
        return ""
    texto = f"{valor:.{casas}f}"
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    if texto in ("", "-"):
        texto = "0"
    return texto.replace(".", ",")
