import pytest


def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _os_em(db_session, os_base, fase):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"], fase=fase, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    return o


@pytest.mark.parametrize("fase,login", [(4, "comum"), (5, "lab"), (6, "comercial"), (7, "comum")])
def test_cancelar_pela_funcao_responsavel(client, usuario_comum, usuario_lab, usuario_comercial, fases_seed, os_base, db_session, fase, login):
    o = _os_em(db_session, os_base, fase)
    h = _headers(client, login, "senha123")
    r = client.post(f"/ordens/{o.id}/cancelar", json={"motivo": "cliente desistiu"}, headers=h)
    assert r.status_code == 200
    assert r.json()["fase"] == 9 and r.json()["situacao"] == "C"
    logs = client.get(f"/ordens/{o.id}/logs", headers=h).json()
    assert any("cliente desistiu" in (l["texto"] or "") for l in logs)


def test_cancelar_admin_sempre_pode(client, usuario_admin, fases_seed, os_base, db_session):
    o = _os_em(db_session, os_base, 5)
    h = _headers(client, "admin", "senha123")
    assert client.post(f"/ordens/{o.id}/cancelar", json={"motivo": "x"}, headers=h).json()["fase"] == 9


def test_cancelar_funcao_errada_403(client, usuario_comum, usuario_lab, fases_seed, os_base, db_session):
    o = _os_em(db_session, os_base, 4)   # responsável = Expedição
    h = _headers(client, "lab", "senha123")
    assert client.post(f"/ordens/{o.id}/cancelar", json={"motivo": "x"}, headers=h).status_code == 403


def test_cancelar_os_encerrada_409(client, usuario_admin, fases_seed, os_base, db_session):
    o = _os_em(db_session, os_base, 9)
    h = _headers(client, "admin", "senha123")
    assert client.post(f"/ordens/{o.id}/cancelar", json={"motivo": "x"}, headers=h).status_code == 409


def test_cancelar_motivo_vazio_422(client, usuario_admin, fases_seed, os_base, db_session):
    o = _os_em(db_session, os_base, 4)
    h = _headers(client, "admin", "senha123")
    assert client.post(f"/ordens/{o.id}/cancelar", json={"motivo": ""}, headers=h).status_code == 422


def test_cancelar_os_inexistente_404(client, usuario_admin, fases_seed):
    h = _headers(client, "admin", "senha123")
    assert client.post("/ordens/9999/cancelar", json={"motivo": "x"}, headers=h).status_code == 404
