import io


def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _pdf():
    return ("cert.pdf", io.BytesIO(b"%PDF-1.4 conteudo"), "application/pdf")


def test_anexar_lista_e_link(client, usuario_lab, db_session, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "CERT_PUBLIC_BASE_URL", "https://x.com")
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.post("/certificados-gerais", data={"nome": "Certificado de Gas 2027"},
                    files={"arquivo": _pdf()}, headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["nome"] == "Certificado de Gas 2027"
    assert body["link"] and "/publico/certificado-geral/" in body["link"]

    itens = client.get("/certificados-gerais", headers=h).json()
    assert len(itens) == 1 and itens[0]["nome"] == "Certificado de Gas 2027"


def test_anexar_exige_permissao_403(client, usuario_comercial, db_session):
    h = _headers(client, "comercial@hs.com", "senha123")
    r = client.post("/certificados-gerais", data={"nome": "X"},
                    files={"arquivo": _pdf()}, headers=h)
    assert r.status_code == 403


def test_anexar_recusa_nao_pdf_415(client, usuario_lab, db_session):
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.post("/certificados-gerais", data={"nome": "X"},
                    files={"arquivo": ("a.png", io.BytesIO(b"x"), "image/png")}, headers=h)
    assert r.status_code == 415


def test_nome_obrigatorio_422(client, usuario_lab, db_session):
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.post("/certificados-gerais", data={"nome": "   "},
                    files={"arquivo": _pdf()}, headers=h)
    assert r.status_code == 422


def test_excluir_remove(client, usuario_lab, db_session):
    from app.models import CertificadoGeral
    h = _headers(client, "lab@hs.com", "senha123")
    cid = client.post("/certificados-gerais", data={"nome": "Gas"},
                      files={"arquivo": _pdf()}, headers=h).json()["id"]
    assert client.delete(f"/certificados-gerais/{cid}", headers=h).status_code == 200
    assert db_session.query(CertificadoGeral).count() == 0
