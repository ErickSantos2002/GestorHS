"""Observacoes da OS: anotacao livre, sem dono de fase, editavel por qualquer
usuario interno em qualquer fase."""


def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _os_na_fase(db, os_base, fase):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"],
              fase=fase, tipo_servico="C", situacao="E")
    db.add(o); db.commit(); db.refresh(o)
    return o.id


def test_funcao_nao_admin_edita_observacoes(client, usuario_lab, fases_seed, os_base, db_session):
    """Laboratorio (nao-admin) escreve: o campo e' anotacao livre, nao tem dono."""
    from app.models import Ordem
    oid = _os_na_fase(db_session, os_base, 5)
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.patch(f"/ordens/{oid}/observacoes", json={"observacoes": "aparelho veio sem tampa"}, headers=h)
    assert r.status_code == 200
    assert r.json()["obs"] == "aparelho veio sem tampa"
    db_session.expire_all()
    assert db_session.get(Ordem, oid).obs == "aparelho veio sem tampa"


def test_edita_observacoes_em_os_finalizada(client, usuario_lab, fases_seed, os_base, db_session):
    """'Qualquer fase' inclui a terminal — a anotacao nao acompanha o fluxo."""
    oid = _os_na_fase(db_session, os_base, 8)
    h = _headers(client, "lab@hs.com", "senha123")
    assert client.patch(f"/ordens/{oid}/observacoes", json={"observacoes": "nota tardia"},
                        headers=h).status_code == 200


def test_edita_observacoes_em_os_cancelada(client, usuario_lab, fases_seed, os_base, db_session):
    oid = _os_na_fase(db_session, os_base, 9)
    h = _headers(client, "lab@hs.com", "senha123")
    assert client.patch(f"/ordens/{oid}/observacoes", json={"observacoes": "motivo do cancelamento"},
                        headers=h).status_code == 200


def test_observacoes_vazia_limpa_o_campo(client, usuario_lab, fases_seed, os_base, db_session):
    """Texto em branco vira None, nao string vazia — o card do TaskHS testa `if ordem.obs`."""
    from app.models import Ordem
    oid = _os_na_fase(db_session, os_base, 5)
    h = _headers(client, "lab@hs.com", "senha123")
    client.patch(f"/ordens/{oid}/observacoes", json={"observacoes": "algo"}, headers=h)
    r = client.patch(f"/ordens/{oid}/observacoes", json={"observacoes": "   "}, headers=h)
    assert r.status_code == 200
    assert r.json()["obs"] is None
    db_session.expire_all()
    assert db_session.get(Ordem, oid).obs is None


def test_edicao_de_observacoes_entra_no_historico(client, usuario_lab, fases_seed, os_base, db_session):
    from app.models import LogOS
    oid = _os_na_fase(db_session, os_base, 5)
    h = _headers(client, "lab@hs.com", "senha123")
    client.patch(f"/ordens/{oid}/observacoes", json={"observacoes": "anotado"}, headers=h)
    logs = db_session.query(LogOS).filter(LogOS.os == oid).all()
    assert any("bserva" in (l.texto or "") for l in logs)


def test_observacoes_sem_token_401(client, fases_seed, os_base, db_session):
    oid = _os_na_fase(db_session, os_base, 5)
    assert client.patch(f"/ordens/{oid}/observacoes", json={"observacoes": "x"}).status_code == 401


def test_observacoes_os_inexistente_404(client, usuario_lab, fases_seed):
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.patch("/ordens/999999/observacoes", json={"observacoes": "x"}, headers=h)
    assert r.status_code == 404
    assert r.json()["detail"] == "OS não encontrada"
