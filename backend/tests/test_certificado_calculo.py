"""A planilha da Qualidade (docs/Certificado Iblow.xlsx, aba BASE DE CALCULO) e a
fonte da verdade destes numeros. Se um teste daqui falhar, a implementacao esta
errada — nao a planilha."""
import pytest

from app.core.certificado_calculo import (
    ParametrosCalculo,
    calcular,
    componente_retangular,
    desvio_padrao_amostral,
    formatar_numero,
)

# Parametros do exemplo da planilha: B1=0,1 / B10=0,1 / B11=0,052 / B12 e B13 vazios / k=2
PARAMS_PLANILHA = ParametrosCalculo(
    valor_referencia=0.1,
    resolucao_instrumento=0.1,
    incerteza_padrao_temp=0.052,
    resolucao_pressao=None,
    incerteza_padrao_pressao=None,
    fator_k=2.0,
)


def test_caso_da_planilha_bate_casa_por_casa():
    r = calcular(["0.16", "0.16", "0.16", "0.16", "0.16"], PARAMS_PLANILHA)
    assert r.erros == [pytest.approx(0.06)] * 5
    assert r.media == pytest.approx(0.16)
    assert r.desvio_padrao == pytest.approx(0.0)
    assert r.incerteza_combinada == pytest.approx(0.06507431649019962)
    assert r.incerteza_expandida == pytest.approx(0.13014863298039925)
    assert r.fator_k == 2.0


def test_desvio_padrao_e_amostral_nao_populacional():
    # amostral (n-1) de [0.15, 0.17] = 0.01414...; populacional seria 0.01
    assert desvio_padrao_amostral([0.15, 0.17]) == pytest.approx(0.014142135623730951)


def test_desvio_padrao_com_menos_de_duas_medicoes_e_zero():
    # STDEV do Excel sobre celula unica/vazia nao explode: aqui tambem nao
    assert desvio_padrao_amostral([]) == 0.0
    assert desvio_padrao_amostral([0.16]) == 0.0


def test_componente_vazio_contribui_zero():
    assert componente_retangular(None) == 0.0
    assert componente_retangular(0.1) == pytest.approx(0.057735026918962584)


def test_medicao_em_branco_e_ignorada_e_seu_erro_sai_none():
    # OS antiga: 3 medicoes preenchidas, 4 e 5 vazias. O erro das vazias e None
    # (sai em branco no certificado), nao -0.1.
    r = calcular(["0.16", "0.16", "0.16", "", None], PARAMS_PLANILHA)
    assert r.medicoes == [pytest.approx(0.16)] * 3
    assert r.erros == [pytest.approx(0.06), pytest.approx(0.06), pytest.approx(0.06), None, None]
    assert r.media == pytest.approx(0.16)


def test_aceita_virgula_como_separador_decimal():
    r = calcular(["0,16"], PARAMS_PLANILHA)
    assert r.medicoes == [pytest.approx(0.16)]


def test_texto_nao_numerico_e_tratado_como_branco():
    r = calcular(["0.16", "abc"], PARAMS_PLANILHA)
    assert r.medicoes == [pytest.approx(0.16)]
    assert r.erros == [pytest.approx(0.06), None]


def test_sem_medicao_nenhuma_nao_explode():
    r = calcular(["", "", "", "", ""], PARAMS_PLANILHA)
    assert r.medicoes == []
    assert r.erros == [None] * 5
    assert r.media is None
    assert r.desvio_padrao == 0.0
    # sem medicao, a incerteza vem so dos componentes fixos
    assert r.incerteza_combinada == pytest.approx(0.06507431649019962)


def test_sem_valor_de_referencia_nao_ha_erro_a_calcular():
    params = ParametrosCalculo(
        valor_referencia=None, resolucao_instrumento=0.1, incerteza_padrao_temp=0.052,
        resolucao_pressao=None, incerteza_padrao_pressao=None, fator_k=2.0,
    )
    r = calcular(["0.16"], params)
    assert r.erros == [None]


def test_formatar_numero_usa_virgula_e_corta_zero_a_direita():
    assert formatar_numero(0.13014863298039925) == "0,1301"
    assert formatar_numero(0.06) == "0,06"
    assert formatar_numero(0.16) == "0,16"
    assert formatar_numero(2.0) == "2"
    assert formatar_numero(None) == ""
