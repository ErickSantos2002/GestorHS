def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _eq(db_session, descricao):
    from app.models import Equipamento
    e = Equipamento(descricao=descricao)
    db_session.add(e); db_session.commit(); db_session.refresh(e)
    return e.id


def test_listar_modelos_flag(client, usuario_admin, db_session):
    h = _headers(client, "admin", "senha123")
    e1 = _eq(db_session, "Mark X")
    e2 = _eq(db_session, "Iblow10")
    client.put(f"/certificados-modelo/{e1}", json={"texto": "<p>a</p>"}, headers=h)
    r = client.get("/certificados-modelo", headers=h).json()
    mapa = {i["equipamento"]: i["tem_certificado"] for i in r["items"]}
    assert mapa[e1] is True
    assert mapa[e2] is False


def test_obter_vazio_quando_sem_certificado(client, usuario_admin, db_session):
    h = _headers(client, "admin", "senha123")
    e = _eq(db_session, "Sem Cert")
    r = client.get(f"/certificados-modelo/{e}", headers=h)
    assert r.status_code == 200
    assert r.json()["texto"] == ""
    assert r.json()["equipamento_descricao"] == "Sem Cert"


def test_upsert_cria_e_atualiza(client, usuario_admin, db_session):
    h = _headers(client, "admin", "senha123")
    e = _eq(db_session, "Up")
    r1 = client.put(f"/certificados-modelo/{e}", json={"texto": "<p>1</p>", "descricao": "d1"}, headers=h)
    assert r1.status_code == 200
    assert r1.json()["texto"] == "<p>1</p>"
    r2 = client.put(f"/certificados-modelo/{e}", json={"texto": "<p>2</p>"}, headers=h)
    assert r2.json()["texto"] == "<p>2</p>"
    assert client.get(f"/certificados-modelo/{e}", headers=h).json()["texto"] == "<p>2</p>"


def test_obter_equipamento_inexistente_404(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    assert client.get("/certificados-modelo/99999", headers=h).status_code == 404


def test_escrita_exige_admin_ou_lab(client, usuario_admin, usuario_comercial, db_session):
    e = _eq(db_session, "Perm")
    h = _headers(client, "comercial", "senha123")
    assert client.put(f"/certificados-modelo/{e}", json={"texto": "x"}, headers=h).status_code == 403


def test_lab_pode_escrever(client, usuario_admin, usuario_lab, db_session):
    e = _eq(db_session, "Lab")
    h = _headers(client, "lab", "senha123")
    assert client.put(f"/certificados-modelo/{e}", json={"texto": "<p>lab</p>"}, headers=h).status_code == 200
