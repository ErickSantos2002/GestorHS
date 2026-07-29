from app.core import proposta_link as pl
from app.core.config import settings


def test_link_none_quando_base_vazia(monkeypatch):
    monkeypatch.setattr(settings, "CERT_PUBLIC_BASE_URL", "")
    assert pl.link_proposta(42) is None


def test_link_completo_com_base(monkeypatch):
    monkeypatch.setattr(settings, "CERT_PUBLIC_BASE_URL", "http://localhost:8001")
    url = pl.link_proposta(42)
    assert url.startswith("http://localhost:8001/publico/proposta/42?t=")
    assert url.endswith(pl.assinar(42))


def test_verificar_aceita_correto_rejeita_adulterado():
    tok = pl.assinar(42)
    assert pl.verificar(42, tok) is True
    assert pl.verificar(42, tok[:-1] + ("0" if tok[-1] != "0" else "1")) is False
    assert pl.verificar(43, tok) is False
    assert pl.verificar(42, "") is False
    assert pl.verificar(42, None) is False


def test_download_ok_com_token_valido(client, monkeypatch):
    from app.api import publico
    monkeypatch.setattr(publico.proposta_pdf, "gerar_pdf", lambda db, pid: b"%PDF-fake")
    tok = pl.assinar(99)
    r = client.get(f"/publico/proposta/99?t={tok}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content == b"%PDF-fake"


def test_403_token_invalido(client):
    r = client.get("/publico/proposta/99?t=errado")
    assert r.status_code == 403


def test_403_token_ausente(client):
    r = client.get("/publico/proposta/99")
    assert r.status_code == 403


def test_404_proposta_inexistente(client, monkeypatch):
    from app.api import publico

    def _raise(db, pid):
        raise ValueError(f"Proposta {pid} nao encontrada")

    monkeypatch.setattr(publico.proposta_pdf, "gerar_pdf", _raise)
    tok = pl.assinar(123)
    r = client.get(f"/publico/proposta/123?t={tok}")
    assert r.status_code == 404
