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
    assert nota_fiscal.nome_download_nota("12345", "abc.xml") == "12345.xml"


def test_nome_download_higieniza_o_numero():
    """O numero e' digitado e vai para o header Content-Disposition — so sai
    daqui com caracteres de nome de arquivo."""
    assert nota_fiscal.nome_download_nota('12/34 "x"', "abc.pdf") == "nota-fiscal-12-34--x-.pdf"


# ── Nome do XML no download: a chave de acesso ─────────────────────────────
# O VIPP (sistema de postagem da expedicao) recusa o XML chamado
# "nota-fiscal-...". O nome que ele aceita e' o que vem do emissor: a chave de
# acesso de 44 digitos. O upload nao guarda o nome original, entao a chave e'
# lida de dentro do proprio XML — o que vale tambem para as notas ja anexadas.
CHAVE = "35261112345678000190550010000123451234567890"

NFE = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">'
    f'<NFe><infNFe Id="NFe{CHAVE}" versao="4.00"><ide/></infNFe></NFe>'
    f'<protNFe><infProt><chNFe>{CHAVE}</chNFe></infProt></protNFe></nfeProc>'
).encode()


def test_chave_de_acesso_do_infnfe():
    assert nota_fiscal.chave_de_acesso(NFE) == CHAVE


def test_chave_de_acesso_so_do_protocolo():
    xml = f"<retConsSitNFe><chNFe>{CHAVE}</chNFe></retConsSitNFe>".encode()
    assert nota_fiscal.chave_de_acesso(xml) == CHAVE


def test_sem_chave_de_acesso():
    assert nota_fiscal.chave_de_acesso(b"<nfse><numero>123</numero></nfse>") is None
    assert nota_fiscal.chave_de_acesso(b"") is None


def test_nome_do_xml_e_a_chave():
    assert nota_fiscal.nome_download_nota("12345", "abc.xml", NFE) == f"{CHAVE}.xml"


def test_nome_do_xml_sem_chave_e_so_o_numero():
    """Sem chave (ex.: XML de NFS-e), o nome e' o numero da nota, sem o prefixo
    que o VIPP recusa."""
    assert nota_fiscal.nome_download_nota("12345", "abc.xml", b"<nfse/>") == "12345.xml"


def test_pdf_nao_muda():
    assert nota_fiscal.nome_download_nota("12345", "abc.pdf", NFE) == "nota-fiscal-12345.pdf"


def test_nome_legado_por_os_usa_a_chave():
    assert nota_fiscal.nome_download(7, "abc.xml", NFE) == f"{CHAVE}.xml"
    assert nota_fiscal.nome_download(7, "abc.xml", b"<nfse/>") == "nota-fiscal-7.xml"
