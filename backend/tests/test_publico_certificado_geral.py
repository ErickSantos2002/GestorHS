import io


def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _anexar(client, db_session):
    h = _headers(client, "lab@hs.com", "senha123")
    return client.post("/certificados-gerais", data={"nome": "Gas"},
                       files={"arquivo": ("g.pdf", io.BytesIO(b"%PDF-1.4 x"), "application/pdf")},
                       headers=h).json()["id"]


def test_download_publico_com_token_valido(client, usuario_lab, db_session):
    from app.core import certificado_geral_link
    cid = _anexar(client, db_session)
    t = certificado_geral_link.assinar(cid)
    r = client.get(f"/publico/certificado-geral/{cid}?t={t}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "inline" in r.headers.get("content-disposition", "")


def test_download_publico_token_invalido_403(client, usuario_lab, db_session):
    cid = _anexar(client, db_session)
    assert client.get(f"/publico/certificado-geral/{cid}?t=errado").status_code == 403


def test_download_publico_inexistente_404(client):
    from app.core import certificado_geral_link
    t = certificado_geral_link.assinar(9999)
    assert client.get(f"/publico/certificado-geral/9999?t={t}").status_code == 404
