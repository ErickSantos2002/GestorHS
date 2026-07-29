import pytest

from app.core import enderecos


def test_validar_cep_aceita_com_e_sem_mascara():
    assert enderecos.validar_cep("50030-230") == "50030230"
    assert enderecos.validar_cep("50030230") == "50030230"


def test_validar_cep_rejeita_tamanho_errado():
    with pytest.raises(enderecos.DocumentoInvalido):
        enderecos.validar_cep("5003023")
    with pytest.raises(enderecos.DocumentoInvalido):
        enderecos.validar_cep("")


def test_validar_cnpj_aceita_com_e_sem_mascara():
    assert enderecos.validar_cnpj("36.312.056/0005-52") == "36312056000552"


def test_validar_cnpj_rejeita_tamanho_errado():
    with pytest.raises(enderecos.DocumentoInvalido):
        enderecos.validar_cnpj("36312056")


def test_capitalizar_texto_da_receita():
    assert enderecos.capitalizar("JOAO NEIVA") == "Joao Neiva"
    assert enderecos.capitalizar("ZONA RURAL") == "Zona Rural"


def test_capitalizar_deixa_conectivos_minusculos_menos_no_inicio():
    assert enderecos.capitalizar("CAIS DO APOLO") == "Cais do Apolo"
    assert enderecos.capitalizar("AVENIDA DAS AMERICAS") == "Avenida das Americas"


def test_capitalizar_preserva_siglas_e_tokens_com_digito():
    assert enderecos.capitalizar("BR 101") == "BR 101"
    assert enderecos.capitalizar("KM 196,5") == "KM 196,5"
    assert enderecos.capitalizar("CBF INDUSTRIA DE GUSA S/A") == "CBF Industria de Gusa S/A"


def test_capitalizar_e_idempotente_e_trata_vazio():
    assert enderecos.capitalizar("Cais do Apolo") == "Cais do Apolo"
    assert enderecos.capitalizar("") == ""
    assert enderecos.capitalizar(None) == ""


def test_mapear_brasilapi_cep():
    dados = {"cep": "50030230", "state": "PE", "city": "RECIFE",
             "neighborhood": "Recife", "street": "CAIS DO APOLO", "service": "open-cep"}
    assert enderecos.mapear_brasilapi_cep(dados) == {
        "cep": "50030230", "endereco": "Cais do Apolo", "municipio": "Recife", "estado": "PE",
    }


def test_mapear_viacep():
    dados = {"cep": "50030-230", "logradouro": "Cais do Apolo", "bairro": "Recife",
             "localidade": "Recife", "uf": "pe"}
    assert enderecos.mapear_viacep(dados) == {
        "cep": "50030230", "endereco": "Cais do Apolo", "municipio": "Recife", "estado": "PE",
    }


def test_mapear_viacep_com_erro_vira_nao_encontrado():
    with pytest.raises(enderecos.NaoEncontrado):
        enderecos.mapear_viacep({"erro": True})
    with pytest.raises(enderecos.NaoEncontrado):
        enderecos.mapear_viacep({"erro": "true"})


def test_mapear_brasilapi_cnpj_monta_endereco_completo():
    dados = {
        "cnpj": "36312056000552", "razao_social": "CBF INDUSTRIA DE GUSA S/A",
        "logradouro": "BR 101", "numero": "S/N", "complemento": "KM 196,5",
        "bairro": "ZONA RURAL", "municipio": "JOAO NEIVA", "uf": "ES", "cep": "29680000",
        "descricao_situacao_cadastral": "ATIVA",
    }
    assert enderecos.mapear_brasilapi_cnpj(dados) == {
        "documento": "36312056000552",
        "nome": "CBF Industria de Gusa S/A",
        "endereco": "BR 101, S/N KM 196,5",
        "municipio": "Joao Neiva",
        "estado": "ES",
        "cep": "29680000",
        "situacao": "ATIVA",
    }


def test_mapear_brasilapi_cnpj_sem_numero_nem_complemento():
    dados = {"cnpj": "36312056000552", "razao_social": "ACME LTDA",
             "logradouro": "RUA X", "numero": "", "complemento": None,
             "municipio": "RECIFE", "uf": "PE", "cep": "50030230",
             "descricao_situacao_cadastral": "ATIVA"}
    r = enderecos.mapear_brasilapi_cnpj(dados)
    assert r["endereco"] == "Rua X"
    assert r["nome"] == "Acme Ltda"


def test_mapear_brasilapi_cnpj_campos_ausentes_viram_string_vazia():
    r = enderecos.mapear_brasilapi_cnpj({"cnpj": "36312056000552"})
    assert r == {"documento": "36312056000552", "nome": "", "endereco": "",
                 "municipio": "", "estado": "", "cep": "", "situacao": ""}
