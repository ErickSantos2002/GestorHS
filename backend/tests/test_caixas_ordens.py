def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _ordem_solta(db_session, nome="Cliente OS"):
    from app.models import Cliente, Ordem
    cli = Cliente(nome=nome)
    db_session.add(cli); db_session.flush()
    o = Ordem(cliente=cli.id, fase=4, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    return o.id


def test_vincular_ordem(client, usuario_comum, fases_seed, db_session):
    h = _headers(client, "comum@hs.com", "senha123")
    cid = client.post("/caixas", json={}, headers=h).json()["id"]
    oid = _ordem_solta(db_session)
    r = client.post(f"/caixas/{cid}/ordens", json={"ordem_id": oid}, headers=h)
    assert r.status_code == 200
    det = client.get(f"/caixas/{cid}", headers=h).json()
    assert [o["id"] for o in det["ordens"]] == [oid]


def test_vincular_permite_clientes_diferentes(client, usuario_comum, fases_seed, db_session):
    h = _headers(client, "comum@hs.com", "senha123")
    cid = client.post("/caixas", json={}, headers=h).json()["id"]
    o1 = _ordem_solta(db_session, "Cliente A")
    o2 = _ordem_solta(db_session, "Cliente B")
    client.post(f"/caixas/{cid}/ordens", json={"ordem_id": o1}, headers=h)
    r = client.post(f"/caixas/{cid}/ordens", json={"ordem_id": o2}, headers=h)
    assert r.status_code == 200
    det = client.get(f"/caixas/{cid}", headers=h).json()
    assert det["total_os"] == 2
    assert det["clientes"] == ["Cliente A", "Cliente B"]


def test_mover_ordem_entre_caixas(client, usuario_comum, fases_seed, db_session):
    h = _headers(client, "comum@hs.com", "senha123")
    c1 = client.post("/caixas", json={}, headers=h).json()["id"]
    c2 = client.post("/caixas", json={}, headers=h).json()["id"]
    oid = _ordem_solta(db_session)
    client.post(f"/caixas/{c1}/ordens", json={"ordem_id": oid}, headers=h)
    client.post(f"/caixas/{c2}/ordens", json={"ordem_id": oid}, headers=h)
    assert client.get(f"/caixas/{c1}", headers=h).json()["total_os"] == 0
    assert client.get(f"/caixas/{c2}", headers=h).json()["total_os"] == 1


def test_desvincular_ordem_e_recusado(client, usuario_comum, fases_seed, db_session):
    """OS sem caixa nao anda: quem avanca de fase e' a caixa. Desvincular deixava
    a OS parada para sempre, sem aparecer em caixa nenhuma — em 24/08/2026 havia
    quatro assim, a mais antiga travada ha um mes."""
    h = _headers(client, "comum@hs.com", "senha123")
    cid = client.post("/caixas", json={}, headers=h).json()["id"]
    oid = _ordem_solta(db_session)
    client.post(f"/caixas/{cid}/ordens", json={"ordem_id": oid}, headers=h)
    r = client.delete(f"/caixas/{cid}/ordens/{oid}", headers=h)
    assert r.status_code == 409
    # A OS continua na caixa — a recusa nao pode ter efeito colateral.
    assert client.get(f"/caixas/{cid}", headers=h).json()["total_os"] == 1


def test_vincular_ordem_inexistente_404(client, usuario_comum):
    h = _headers(client, "comum@hs.com", "senha123")
    cid = client.post("/caixas", json={}, headers=h).json()["id"]
    assert client.post(f"/caixas/{cid}/ordens", json={"ordem_id": 9999}, headers=h).status_code == 404


def test_mover_ordem_entre_caixas(client, usuario_comum, fases_seed, db_session):
    """O caminho que substitui o desvincular: tirar a OS de uma caixa e' move-la
    para outra, nunca deixa-la solta."""
    h = _headers(client, "comum@hs.com", "senha123")
    c1 = client.post("/caixas", json={}, headers=h).json()["id"]
    c2 = client.post("/caixas", json={}, headers=h).json()["id"]
    oid = _ordem_solta(db_session)
    client.post(f"/caixas/{c1}/ordens", json={"ordem_id": oid}, headers=h)
    assert client.post(f"/caixas/{c2}/ordens", json={"ordem_id": oid}, headers=h).status_code == 200
    assert client.get(f"/caixas/{c1}", headers=h).json()["total_os"] == 0
    assert client.get(f"/caixas/{c2}", headers=h).json()["total_os"] == 1
