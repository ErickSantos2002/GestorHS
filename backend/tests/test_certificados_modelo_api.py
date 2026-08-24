def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _eq(db_session, descricao):
    from app.models import Equipamento
    e = Equipamento(descricao=descricao)
    db_session.add(e); db_session.commit(); db_session.refresh(e)
    return e.id


def test_listar_flags_por_tipo(client, usuario_admin, db_session):
    h = _headers(client, "admin@hs.com", "senha123")
    e = _eq(db_session, "Mark X")
    client.put(f"/certificados-modelo/{e}?tipo=C", json={"texto": "<p>c</p>"}, headers=h)
    r = client.get("/certificados-modelo", headers=h).json()
    item = next(i for i in r["items"] if i["equipamento"] == e)
    assert item["tem_calibracao"] is True
    assert item["tem_manutencao"] is False


def test_get_put_por_aparelho_e_so_calibracao(client, usuario_admin, db_session):
    """Manutencao saiu desta rota: tem modelo UNICO, em /certificados-modelo/generico.

    Um modelo de manutencao por aparelho venceria o generico em silencio (ver
    `modelo_para`), e aquele aparelho pararia de acompanhar as revisoes da
    Qualidade sem aviso.
    """
    h = _headers(client, "admin@hs.com", "senha123")
    e = _eq(db_session, "Iblow")
    client.put(f"/certificados-modelo/{e}?tipo=C", json={"texto": "<p>cal</p>"}, headers=h)
    assert client.get(f"/certificados-modelo/{e}?tipo=C", headers=h).json()["texto"] == "<p>cal</p>"
    assert client.put(f"/certificados-modelo/{e}?tipo=M", json={"texto": "<p>man</p>"}, headers=h).status_code == 422
    assert client.get(f"/certificados-modelo/{e}?tipo=M", headers=h).status_code == 422


def test_tipo_default_c(client, usuario_admin, db_session):
    h = _headers(client, "admin@hs.com", "senha123")
    e = _eq(db_session, "Def")
    client.put(f"/certificados-modelo/{e}", json={"texto": "<p>x</p>"}, headers=h)  # sem tipo => C
    assert client.get(f"/certificados-modelo/{e}", headers=h).json()["texto"] == "<p>x</p>"
    assert client.get(f"/certificados-modelo/{e}?tipo=C", headers=h).json()["texto"] == "<p>x</p>"


def test_obter_equipamento_inexistente_404(client, usuario_admin):
    h = _headers(client, "admin@hs.com", "senha123")
    assert client.get("/certificados-modelo/99999", headers=h).status_code == 404


def test_upsert_equipamento_inexistente_404(client, usuario_admin):
    h = _headers(client, "admin@hs.com", "senha123")
    assert client.put("/certificados-modelo/99999", json={"texto": "x"}, headers=h).status_code == 404


def test_tipo_invalido_422(client, usuario_admin, db_session):
    h = _headers(client, "admin@hs.com", "senha123")
    e = _eq(db_session, "Inv")
    assert client.get(f"/certificados-modelo/{e}?tipo=X", headers=h).status_code == 422


def test_escrita_exige_admin_ou_lab(client, usuario_admin, usuario_comercial, db_session):
    e = _eq(db_session, "Perm")
    h = _headers(client, "comercial@hs.com", "senha123")
    assert client.put(f"/certificados-modelo/{e}", json={"texto": "x"}, headers=h).status_code == 403


def test_lab_pode_escrever(client, usuario_admin, usuario_lab, db_session):
    e = _eq(db_session, "Lab")
    h = _headers(client, "lab@hs.com", "senha123")
    assert client.put(f"/certificados-modelo/{e}?tipo=C", json={"texto": "<p>lab</p>"}, headers=h).status_code == 200
