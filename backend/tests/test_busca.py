"""Quando o termo de busca vale como documento.

Nasceu do falso positivo de 16/09/2026: a serie `WAO4O0065` virava os digitos
`40065` e trazia tres clientes cujo CNPJ tinha `40065` no meio.
"""

from app.core.busca import digitos_de_documento


def test_termo_so_de_digitos_e_documento():
    assert digitos_de_documento("01899414000167") == "01899414000167"


def test_termo_com_pontuacao_de_documento_vira_digitos():
    assert digitos_de_documento("01.899.414/0001-67") == "01899414000167"


def test_documento_parcial_colado_continua_valendo():
    assert digitos_de_documento("01.899") == "01899"


def test_termo_com_letra_nao_e_documento():
    """A serie do falso positivo: nao pode virar busca por CNPJ."""
    assert digitos_de_documento("WAO4O0065") is None


def test_serie_com_hifen_e_digitos_nao_e_documento():
    assert digitos_de_documento("WATFR01-00179") is None


def test_termo_sem_digito_nenhum_nao_e_documento():
    assert digitos_de_documento("Sorocaba") is None


def test_termo_vazio_ou_so_pontuacao_nao_e_documento():
    assert digitos_de_documento("") is None
    assert digitos_de_documento("  ") is None
    assert digitos_de_documento("-/.") is None
