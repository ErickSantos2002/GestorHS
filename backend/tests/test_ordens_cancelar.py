"""Cancelar UMA OS, so pelo Administrador (POST /ordens/{id}/cancelar).

O caminho normal e' cancelar a CAIXA inteira. Este endpoint existe para a OS que
nao deveria ter sido aberta e esta atrapalhando uma caixa que segue viva: some das
contas (`_ordens_ativas`) e do card do TaskHS (`ordens_do_card`), mas continua
apontando para a caixa — o vinculo e' o rastro de que o aparelho passou por ali.
"""
import pytest

from app.models import Caixa, LogOS, Ordem


@pytest.fixture()
def caixa_lab_duas_os(db_session, fases_seed):
    """Caixa em fase 5 com DUAS OS ativas. Devolve {caixa, a, b}."""
    from app.models import Cliente
    cli = Cliente(nome="Cliente Cancelar")
    cx = Caixa(obs="Caixa cancelar", fase=5)
    db_session.add_all([cli, cx])
    db_session.flush()
    a = Ordem(cliente=cli.id, fase=5, situacao="E", caixa=cx.id)
    b = Ordem(cliente=cli.id, fase=5, situacao="E", caixa=cx.id)
    db_session.add_all([a, b])
    db_session.commit()
    return {"caixa": cx.id, "a": a.id, "b": b.id}


def test_admin_cancela_os_marca_fase_9_e_situacao_c(client_admin, caixa_lab_duas_os):
    r = client_admin.post(f"/ordens/{caixa_lab_duas_os['a']}/cancelar",
                          json={"motivo": "OS aberta por engano"})
    assert r.status_code == 200
    body = r.json()
    assert body["fase"] == 9
    assert body["situacao"] == "C"


def test_cancelar_mantem_o_vinculo_com_a_caixa(client_admin, caixa_lab_duas_os):
    """O vinculo e' o rastro — a OS cancelada continua apontando para a caixa."""
    r = client_admin.post(f"/ordens/{caixa_lab_duas_os['a']}/cancelar",
                          json={"motivo": "engano"})
    assert r.json()["caixa"] == caixa_lab_duas_os["caixa"]


def test_cancelar_uma_de_duas_deixa_a_caixa_na_fase(client_admin, caixa_lab_duas_os, db_session):
    r = client_admin.post(f"/ordens/{caixa_lab_duas_os['a']}/cancelar", json={"motivo": "engano"})
    assert r.status_code == 200
    db_session.expire_all()
    assert db_session.get(Caixa, caixa_lab_duas_os["caixa"]).fase == 5
    assert db_session.get(Ordem, caixa_lab_duas_os["b"]).fase == 5


def test_cancelar_a_ultima_os_ativa_arquiva_a_caixa(client_admin, caixa_lab_duas_os, db_session):
    """Caixa sem nenhuma OS ativa nao tem o que avancar — arquiva (fase None),
    igual ao que `cancelar_caixa` faz."""
    for chave in ("a", "b"):
        r = client_admin.post(f"/ordens/{caixa_lab_duas_os[chave]}/cancelar", json={"motivo": "engano"})
        assert r.status_code == 200
    db_session.expire_all()
    assert db_session.get(Caixa, caixa_lab_duas_os["caixa"]).fase is None


def test_cancelar_registra_o_motivo_no_log(client_admin, caixa_lab_duas_os, db_session):
    client_admin.post(f"/ordens/{caixa_lab_duas_os['a']}/cancelar",
                      json={"motivo": "duplicada da 11207"})
    logs = db_session.query(LogOS).filter(LogOS.os == caixa_lab_duas_os["a"]).all()
    assert any("duplicada da 11207" in (l.texto or "") for l in logs)


def test_cancelar_sem_motivo_e_recusado(client_admin, caixa_lab_duas_os):
    r = client_admin.post(f"/ordens/{caixa_lab_duas_os['a']}/cancelar", json={"motivo": ""})
    assert r.status_code == 422


def test_cancelar_os_ja_cancelada_devolve_409(client_admin, caixa_lab_duas_os):
    primeira = client_admin.post(f"/ordens/{caixa_lab_duas_os['a']}/cancelar", json={"motivo": "engano"})
    assert primeira.status_code == 200
    r = client_admin.post(f"/ordens/{caixa_lab_duas_os['a']}/cancelar", json={"motivo": "de novo"})
    assert r.status_code == 409


def test_cancelar_os_finalizada_devolve_409(client_admin, caixa_lab_duas_os, db_session):
    o = db_session.get(Ordem, caixa_lab_duas_os["a"])
    o.fase = 8
    db_session.commit()
    r = client_admin.post(f"/ordens/{o.id}/cancelar", json={"motivo": "tarde demais"})
    assert r.status_code == 409


def test_cancelar_exige_administrador(client_lab, caixa_lab_duas_os):
    """Cancelar a CAIXA e' da funcao da fase; cancelar UMA OS e' so do Administrador."""
    r = client_lab.post(f"/ordens/{caixa_lab_duas_os['a']}/cancelar", json={"motivo": "engano"})
    assert r.status_code == 403


def test_cancelar_os_inexistente_devolve_404(client_admin):
    r = client_admin.post("/ordens/999999/cancelar", json={"motivo": "engano"})
    assert r.status_code == 404
