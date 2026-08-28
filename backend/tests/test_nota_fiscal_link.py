from app.core import nota_fiscal_link as nl
from app.core.config import settings


def test_assinar_deterministico_e_varia_por_os():
    assert nl.assinar(1234) == nl.assinar(1234)
    assert nl.assinar(1234) != nl.assinar(1235)


def test_verificar_aceita_correto_rejeita_adulterado():
    tok = nl.assinar(1234)
    assert nl.verificar(1234, tok) is True
    assert nl.verificar(1234, tok[:-1] + ("0" if tok[-1] != "0" else "1")) is False
    assert nl.verificar(1235, tok) is False
    assert nl.verificar(1234, "") is False
    assert nl.verificar(1234, None) is False


def test_token_da_nf_difere_do_token_do_certificado():
    """Dominios separados: o token da NF nao pode servir para o certificado."""
    from app.core import certificado_link as cl
    assert nl.assinar(1234) != cl.assinar(1234, "C")


def test_link_none_sem_base(monkeypatch):
    monkeypatch.setattr(settings, "CERT_PUBLIC_BASE_URL", "")
    assert nl.link_nota_fiscal(1234) is None


def test_link_completo_com_base(monkeypatch):
    monkeypatch.setattr(settings, "CERT_PUBLIC_BASE_URL", "http://localhost:8001")
    url = nl.link_nota_fiscal(1234)
    assert url.startswith("http://localhost:8001/publico/nota-fiscal/1234?t=")
    assert url.endswith(nl.assinar(1234))


def test_token_do_xml_difere_do_token_do_pdf():
    """Dominios separados: o token do PDF nao pode baixar o XML e vice-versa."""
    assert nl.assinar(1234, nl.XML) != nl.assinar(1234)
    assert nl.verificar(1234, nl.assinar(1234, nl.XML)) is False
    assert nl.verificar(1234, nl.assinar(1234), nl.XML) is False


def test_verificar_xml_aceita_correto_rejeita_adulterado():
    tok = nl.assinar(1234, nl.XML)
    assert nl.verificar(1234, tok, nl.XML) is True
    assert nl.verificar(1235, tok, nl.XML) is False
    assert nl.verificar(1234, None, nl.XML) is False


def test_link_xml_none_sem_base(monkeypatch):
    monkeypatch.setattr(settings, "CERT_PUBLIC_BASE_URL", "")
    assert nl.link_nota_fiscal_xml(1234) is None


def test_link_xml_completo_com_base(monkeypatch):
    monkeypatch.setattr(settings, "CERT_PUBLIC_BASE_URL", "http://localhost:8001")
    url = nl.link_nota_fiscal_xml(1234)
    assert url.startswith("http://localhost:8001/publico/nota-fiscal/1234/xml?t=")
    assert url.endswith(nl.assinar(1234, nl.XML))
