"""Fase 2b do Guardi: o Laboratorio gera certificado de calibracao pelo token de
agente. O agente nao toca em cert_overrides; desfecho-lab segue fechado."""
import pytest

from app.models import (Caixa, CertificadoModelo, Cliente, Equipamento, EquipamentoCliente,
                        LogOS, Ordem)

CABECALHO = {"nomecli": "NOME AJUSTADO NA TELA", "cnpj": "12.345.678/0001-90"}


@pytest.fixture()
def como(client, fases_seed, agente):
    def _como(email):
        client.headers["Authorization"] = f"Bearer {agente(email)}"
        return client
    return _como


@pytest.fixture()
def os_lab(db_session):
    cat = Equipamento(descricao="Mark-X"); db_session.add(cat); db_session.flush()
    cli = Cliente(nome="ACME"); db_session.add(cli); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=cat.id, serie="S1")
    cx = Caixa(obs="lab", fase=5)
    db_session.add_all([ec, cx]); db_session.flush()
    o = Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=5, situacao="E", tipo_servico="C",
              caixa=cx.id, desfecho_lab="pendente", cert_overrides=dict(CABECALHO))
    db_session.add(o)
    db_session.add(CertificadoModelo(equipamento=cat.id, tipo="C", texto="<p>[nomecli]|[cnpj]|[serie]</p>"))
    db_session.commit()
    return o.id


def _logs(db, oid):
    return [l.texto for l in db.query(LogOS).filter(LogOS.os == oid)]


def test_laboratorio_gera_e_conclui(como, usuario_lab, os_lab, db_session):
    r = como("lab@hs.com").post(f"/ordens/{os_lab}/gerar-certificado",
                                json={"calib_cert": "123", "calib_situacao": "Aprovado"})
    assert r.status_code == 200, r.text
    [cert] = r.json()
    assert cert["tipo"] == "C" and cert["html"] is None  # o agente fica com o link_pdf
    o = db_session.get(Ordem, os_lab); db_session.refresh(o)
    assert o.desfecho_lab == "concluido"
    assert o.calib_cert == "123"
    assert "Laboratório concluído — certificado gerado via erick-bot" in _logs(db_session, os_lab)


def test_leitura_dos_campos(como, usuario_lab, os_lab):
    r = como("lab@hs.com").get(f"/ordens/{os_lab}/certificado-campos")
    assert r.status_code == 200
    assert r.json()["nomecli"] == CABECALHO["nomecli"]


@pytest.mark.parametrize("corpo", [
    {"calib_cert": "1"},                                  # corpo sem override: na tela zeraria
    {"calib_cert": "1", "nomecli": "OUTRO", "serie": "X"},  # override no corpo: ignorado
])
def test_agente_nao_mexe_no_cabecalho(como, usuario_lab, os_lab, db_session, corpo):
    r = como("lab@hs.com").post(f"/ordens/{os_lab}/gerar-certificado", json=corpo)
    assert r.status_code == 200, r.text
    o = db_session.get(Ordem, os_lab); db_session.refresh(o)
    assert o.cert_overrides == CABECALHO
    from app.models import OSCertificado
    html = db_session.query(OSCertificado).filter(OSCertificado.os == os_lab).one().html
    assert html == f"<p>{CABECALHO['nomecli']}|{CABECALHO['cnpj']}|S1</p>"


def test_regerar_log_via(como, usuario_lab, os_lab, db_session):
    c = como("lab@hs.com")
    c.post(f"/ordens/{os_lab}/gerar-certificado", json={})
    c.post(f"/ordens/{os_lab}/gerar-certificado", json={})
    assert "Certificado regerado via erick-bot" in _logs(db_session, os_lab)


@pytest.mark.parametrize("fixture_usuario,email", [("usuario_comum", "comum@hs.com"),
                                                   ("usuario_consulta", "consulta@hs.com")])
def test_expedicao_e_consulta_403(como, os_lab, db_session, request, fixture_usuario, email):
    request.getfixturevalue(fixture_usuario)
    r = como(email).post(f"/ordens/{os_lab}/gerar-certificado", json={})
    assert r.status_code == 403
    o = db_session.get(Ordem, os_lab); db_session.refresh(o)
    assert o.desfecho_lab == "pendente"


def test_desfecho_lab_fechado_ao_agente(como, usuario_lab, os_lab):
    r = como("lab@hs.com").post(f"/ordens/{os_lab}/desfecho-lab", json={"desfecho": "liberado"})
    assert r.status_code == 403
    assert r.json()["detail"] == "Ação não permitida para o agente"


def test_tela_continua_gravando_override(client, usuario_lab, fases_seed, os_lab, db_session):
    tok = client.post("/auth/login", json={"email": "lab@hs.com", "senha": "senha123"}).json()
    r = client.post(f"/ordens/{os_lab}/gerar-certificado", json={"nomecli": "PELA TELA"},
                    headers={"Authorization": f"Bearer {tok['access_token']}"})
    assert r.status_code == 200
    assert r.json()[0]["html"]  # a tela recebe o html
    o = db_session.get(Ordem, os_lab); db_session.refresh(o)
    assert o.cert_overrides == {"nomecli": "PELA TELA"}
