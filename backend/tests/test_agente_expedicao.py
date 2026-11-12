"""Fase 2a do Guardi: as tres escritas abertas ao token de agente (POST /ordens,
POST /caixas/{id}/avancar, POST /equipamentos-cliente), valendo a funcao do DONO.
Toda outra escrita segue 403 (varredura em test_funcao_consulta.py)."""
import pytest

from app.models import Caixa, LogOS, Ordem

MSG_AGENTE = "Ação não permitida para o agente"


@pytest.fixture()
def como(client, fases_seed, agente):
    """como(email): poe no client o token de agente em nome daquele usuario."""
    def _como(email):
        client.headers["Authorization"] = f"Bearer {agente(email)}"
        return client
    return _como


def _caixa(db, os_base, fase, desfecho=None):
    cx = Caixa(obs="lote guardi", fase=fase)
    db.add(cx); db.flush()
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"],
              fase=fase, situacao="E", tipo_servico="C", caixa=cx.id, desfecho_lab=desfecho)
    db.add(o); db.commit()
    return cx.id, o.id


def _abrir(c, os_base):
    return c.post("/ordens", json={"equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C"})


def test_expedicao_abre_os_com_via_no_log(como, usuario_comum, os_base, db_session):
    r = _abrir(como("comum@hs.com"), os_base)
    assert r.status_code == 201, r.text
    textos = [l.texto for l in db_session.query(LogOS).filter(LogOS.os == r.json()["id"])]
    assert "OS aberta — Recebido via erick-bot" in textos
    assert all(t.endswith("via erick-bot") for t in textos)


def test_expedicao_avanca_caixa_em_recebido(como, usuario_comum, os_base, db_session):
    cx, os_id = _caixa(db_session, os_base, fase=4)
    r = como("comum@hs.com").post(f"/caixas/{cx}/avancar", json={})
    assert r.status_code == 200, r.text
    assert r.json()["fase"] == 5
    assert any(l.texto.endswith("via erick-bot")
               for l in db_session.query(LogOS).filter(LogOS.os == os_id))


def test_expedicao_cadastra_aparelho(como, usuario_comum, os_base):
    r = como("comum@hs.com").post("/equipamentos-cliente", json={
        "cliente": os_base["cliente"], "equipamento": os_base["equipamento"], "serie": "GUARDI-1"})
    assert r.status_code == 201, r.text


def test_consulta_recusada_nas_tres(como, usuario_consulta, os_base, db_session):
    cx, _ = _caixa(db_session, os_base, fase=4)
    c = como("consulta@hs.com")
    for resp in (_abrir(c, os_base),
                 c.post(f"/caixas/{cx}/avancar", json={}),
                 c.post("/equipamentos-cliente", json={"cliente": os_base["cliente"],
                                                       "equipamento": os_base["equipamento"]})):
        assert resp.status_code == 403, resp.text


def test_laboratorio_avanca_no_lab_e_nao_em_recebido(como, usuario_lab, os_base, db_session):
    cx_lab, _ = _caixa(db_session, os_base, fase=5, desfecho="liberado")
    cx_rec, _ = _caixa(db_session, os_base, fase=4)
    c = como("lab@hs.com")
    assert c.post(f"/caixas/{cx_lab}/avancar", json={}).status_code == 200
    assert c.post(f"/caixas/{cx_rec}/avancar", json={}).status_code == 403
    # e nao abre OS: a rota exige Expedicao/Administrador
    assert _abrir(c, os_base).status_code == 403


def test_sem_nota_fiscal_recusado_mesmo_para_admin(como, usuario_admin, os_base, db_session):
    cx, _ = _caixa(db_session, os_base, fase=10)
    r = como("admin@hs.com").post(f"/caixas/{cx}/avancar", json={"sem_nota_fiscal": True})
    assert r.status_code == 403
    assert "agente" in r.json()["detail"]
    assert db_session.get(Caixa, cx).fase == 10


def test_outra_escrita_403(como, usuario_admin, os_base, db_session):
    cx, _ = _caixa(db_session, os_base, fase=4)
    r = como("admin@hs.com").post(f"/caixas/{cx}/cancelar", json={"motivo": "teste"})
    assert r.status_code == 403
    assert r.json()["detail"] == MSG_AGENTE


def test_login_normal_depois_do_agente_nao_leva_via(como, usuario_comum, os_base, db_session):
    # db_session e' o mesmo objeto entre requests do teste: o via do agente nao pode vazar.
    assert _abrir(como("comum@hs.com"), os_base).status_code == 201
    c = como("comum@hs.com")
    tok = c.post("/auth/login", json={"email": "comum@hs.com", "senha": "senha123"}).json()
    c.headers["Authorization"] = f"Bearer {tok['access_token']}"
    cx, os_id = _caixa(db_session, os_base, fase=4)
    assert c.post(f"/caixas/{cx}/avancar", json={}).status_code == 200
    assert not any("via" in (l.texto or "") for l in db_session.query(LogOS).filter(LogOS.os == os_id))
