"""Convencao de onde os arquivos de nota fiscal ficam no disco.

A nota nova vive no subdir da CAIXA. A nota do backfill da 0029 aponta para o
subdir da OS, porque e' onde o arquivo ja estava — a migracao nao move nada.
"""
from app.core import nota_fiscal


def test_subdir_da_caixa():
    assert nota_fiscal.subdir_caixa(42) == "notas-fiscais/caixa/42"


def test_subdir_de_nota_nova_e_o_da_caixa():
    assert nota_fiscal.subdir_nota(None, 42) == "notas-fiscais/caixa/42"


def test_subdir_de_nota_do_backfill_e_o_da_os():
    """`ordem` preenchido so acontece no backfill: os arquivos ficaram la."""
    assert nota_fiscal.subdir_nota(777, 42) == nota_fiscal.subdir(777)
    assert nota_fiscal.subdir_nota(777, 42) == "notas-fiscais/777"


def test_nome_download_usa_o_numero_da_nota():
    assert nota_fiscal.nome_download_nota("12345", "abc.pdf") == "nota-fiscal-12345.pdf"
    assert nota_fiscal.nome_download_nota("12345", "abc.xml") == "nota-fiscal-12345.xml"


def test_nome_download_higieniza_o_numero():
    """O numero e' digitado e vai para o header Content-Disposition — so sai
    daqui com caracteres de nome de arquivo."""
    assert nota_fiscal.nome_download_nota('12/34 "x"', "abc.pdf") == "nota-fiscal-12-34--x-.pdf"
