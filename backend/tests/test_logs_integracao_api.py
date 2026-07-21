def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _seed(db_session):
    from app.models import LogIntegracao
    db_session.add_all([
        LogIntegracao(integracao="growthhs", tipo="os_card", external_id="10853",
                      referencia_os=10853, status="sucesso", http_status=200),
        LogIntegracao(integracao="growthhs", tipo="os_card", external_id="10854",
                      referencia_os=10854, status="erro", http_status=422, resposta="ruim"),
        LogIntegracao(integracao="taskhs", tipo="os_espelho", external_id="10853",
                      referencia_os=10853, status="pulado", motivo="desligado"),
    ])
    db_session.commit()


def test_lista_exige_admin(client, usuario_comum, db_session):
    h = _headers(client, "comum@hs.com", "senha123")
    assert client.get("/logs-integracao", headers=h).status_code == 403


def test_lista_retorna_tudo_e_estado(client, usuario_admin, db_session):
    _seed(db_session)
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.get("/logs-integracao", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert set(body["estado"].keys()) == {"taskhs_ativo", "growthhs_ativo"}


def test_filtra_por_status_e_integracao(client, usuario_admin, db_session):
    _seed(db_session)
    h = _headers(client, "admin@hs.com", "senha123")
    assert client.get("/logs-integracao?status=erro", headers=h).json()["total"] == 1
    assert client.get("/logs-integracao?integracao=taskhs", headers=h).json()["total"] == 1
    assert client.get("/logs-integracao?os=10853", headers=h).json()["total"] == 2
