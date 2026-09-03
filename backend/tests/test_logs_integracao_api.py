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


def test_reenviar_sem_payload_409(client, usuario_admin, db_session):
    from app.models import LogIntegracao
    row = LogIntegracao(integracao="growthhs", tipo="os_card", status="pulado",
                        motivo="sem_equipamento", referencia_os=1, payload=None)
    db_session.add(row); db_session.commit(); db_session.refresh(row)
    h = _headers(client, "admin@hs.com", "senha123")
    assert client.post(f"/logs-integracao/{row.id}/reenviar", headers=h).status_code == 409


def test_reenviar_ok(client, usuario_admin, db_session, monkeypatch):
    from app.models import LogIntegracao
    from app.api import logs_integracao
    row = LogIntegracao(integracao="growthhs", tipo="os_card", external_id="10853",
                        status="erro", payload={"source": "gestorhs.os", "external_id": "10853"})
    db_session.add(row); db_session.commit(); db_session.refresh(row)
    monkeypatch.setattr(logs_integracao.hsgrowth_client, "enviar_card_sync",
                        lambda payload: {"created": True})
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.post(f"/logs-integracao/{row.id}/reenviar", headers=h)
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_reenviar_exige_admin(client, usuario_comum, db_session):
    h = _headers(client, "comum@hs.com", "senha123")
    assert client.post("/logs-integracao/1/reenviar", headers=h).status_code == 403


def test_referencia_tipo_separa_caixa_de_os(client, usuario_admin, db_session):
    """A tela linka para a caixa ou para a OS conforme o que o numero representa."""
    from app.models import LogIntegracao
    db_session.add_all([
        # card de caixa (o normal desde set/2026)
        LogIntegracao(integracao="taskhs", tipo="os_espelho", external_id="916",
                      referencia_os=916, status="sucesso", http_status=200,
                      payload={"external_id": "916", "title": "CX 916 · ACME · 2 aparelhos"}),
        # linha antiga, de quando existia card por OS
        LogIntegracao(integracao="taskhs", tipo="os_espelho", external_id="10992",
                      referencia_os=10992, status="sucesso", http_status=200,
                      payload={"external_id": "10992", "title": "CX 916 · OS #10992 · ACME"}),
        # pulo por modulo: sem payload, referencia gravada com o id da OS
        LogIntegracao(integracao="taskhs", tipo="os_espelho", referencia_os=11181,
                      status="pulado", motivo="caixa_de_modulo"),
    ])
    db_session.commit()
    h = _headers(client, "admin@hs.com", "senha123")
    itens = client.get("/logs-integracao", headers=h).json()["items"]
    por_ref = {i["referencia_os"]: i["referencia_tipo"] for i in itens}
    assert por_ref[916] == "caixa"
    assert por_ref[10992] == "os"
    assert por_ref[11181] == "os"


def test_referencia_tipo_none_quando_linha_nao_referencia_nada(client, usuario_admin, db_session):
    from app.models import LogIntegracao
    db_session.add(LogIntegracao(integracao="growthhs", tipo="vencendo",
                                 external_id="7794:2027-07", status="sucesso",
                                 payload={"external_id": "7794:2027-07"}))
    db_session.commit()
    h = _headers(client, "admin@hs.com", "senha123")
    itens = client.get("/logs-integracao", headers=h).json()["items"]
    assert itens[0]["referencia_tipo"] is None
