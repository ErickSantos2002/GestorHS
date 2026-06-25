from app.core import certificado_link as cl
from app.core.config import settings


def test_assinar_deterministico():
    a = cl.assinar(1234, "C")
    b = cl.assinar(1234, "C")
    assert a == b and len(a) == 64  # sha256 hex


def test_assinar_varia_por_os_e_tipo():
    assert cl.assinar(1234, "C") != cl.assinar(1234, "M")
    assert cl.assinar(1234, "C") != cl.assinar(1235, "C")


def test_verificar_aceita_correto_rejeita_adulterado():
    tok = cl.assinar(1234, "C")
    assert cl.verificar(1234, "C", tok) is True
    assert cl.verificar(1234, "C", tok[:-1] + ("0" if tok[-1] != "0" else "1")) is False
    assert cl.verificar(1234, "M", tok) is False
    assert cl.verificar(1234, "C", "") is False
    assert cl.verificar(1234, "C", None) is False


def test_link_none_quando_base_vazia(monkeypatch):
    monkeypatch.setattr(settings, "CERT_PUBLIC_BASE_URL", "")
    assert cl.link_certificado(1234, "C") is None


def test_link_completo_com_base(monkeypatch):
    monkeypatch.setattr(settings, "CERT_PUBLIC_BASE_URL", "http://localhost:8001")
    url = cl.link_certificado(1234, "C")
    assert url.startswith("http://localhost:8001/publico/certificado/1234/calibracao?t=")
    assert url.endswith(cl.assinar(1234, "C"))
