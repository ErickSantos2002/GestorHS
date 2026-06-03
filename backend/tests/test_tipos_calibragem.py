def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_listar_tipos_calibragem(client, usuario_comum, db_session):
    from app.models import TipoCalibragem
    db_session.add(TipoCalibragem(descricao="Calibração Anual"))
    db_session.commit()
    h = _headers(client, "comum", "senha123")
    r = client.get("/tipos-calibragem", headers=h)
    assert r.status_code == 200
    assert any(t["descricao"] == "Calibração Anual" for t in r.json())


def test_tipos_calibragem_exige_auth(client):
    assert client.get("/tipos-calibragem").status_code == 401
