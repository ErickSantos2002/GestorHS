import io


def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _png_bytes():
    import base64
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )


def test_upload_listar_excluir(client, usuario_admin, upload_tmp):
    h = _headers(client, "admin", "senha123")
    files = {"file": ("logo.png", io.BytesIO(_png_bytes()), "image/png")}
    r = client.post("/certificado-imagens", data={"nome": "Logo"}, files=files, headers=h)
    assert r.status_code == 201, r.text
    img = r.json()
    assert img["nome"] == "Logo"
    assert img["url"].startswith("/certificado-imagens/arquivo/")
    lista = client.get("/certificado-imagens", headers=h).json()
    assert any(i["id"] == img["id"] for i in lista["items"])
    assert client.delete(f"/certificado-imagens/{img['id']}", headers=h).status_code == 204


def test_serve_publico_sem_token(client, usuario_admin, upload_tmp):
    h = _headers(client, "admin", "senha123")
    files = {"file": ("a.png", io.BytesIO(_png_bytes()), "image/png")}
    arquivo = client.post("/certificado-imagens", files=files, headers=h).json()["arquivo"]
    r = client.get(f"/certificado-imagens/arquivo/{arquivo}")  # SEM auth
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/")


def test_serve_path_traversal_bloqueado(client):
    r = client.get("/certificado-imagens/arquivo/..%2f..%2fsecret")
    assert r.status_code in (400, 404)


def test_upload_exige_admin_ou_lab(client, usuario_admin, usuario_comercial, upload_tmp):
    h = _headers(client, "comercial", "senha123")
    files = {"file": ("a.png", io.BytesIO(_png_bytes()), "image/png")}
    assert client.post("/certificado-imagens", files=files, headers=h).status_code == 403
