from datetime import date


def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _modelo(db_session, equipamento_id,
            texto="<p>[nomecli] | [serie] | [calibcert] | [os] | [proxcalibragem]</p>"):
    from app.models import CertificadoModelo
    db_session.add(CertificadoModelo(equipamento=equipamento_id, tipo="C", texto=texto))
    db_session.commit()


def _payload(**kw):
    base = {
        "calib_cert": "V-001",
        "data_calibracao": "2026-07-20",
        "prox_calibragem": "2027-07-20",
        "calib_temp": "22", "calib_pressao": "1013",
        "calib_teste1": "0,10", "calib_teste2": "0,11", "calib_teste3": "0,12",
        "calib_teste_media": "0,11", "calib_situacao": "Aparelho inicial",
    }
    base.update(kw)
    return base


def test_campos_vem_preenchidos_do_cadastro(client, usuario_lab, os_base, db_session):
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.get(f"/equipamentos-cliente/{os_base['equipamento_cliente']}/certificado-venda-campos", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["nomecli"] == "Cliente OS"
    assert body["serie"] == "SER-1"
    assert body["patrimonio"] == "PAT-1"
    assert body["calib_situacao"] == "Aparelho inicial"     # default da venda
    assert body["data_calibracao"] == date.today().isoformat()
    assert body["ja_gerado"] is False


def test_gerar_salva_preenche_o_html_e_espelha_na_frota(client, usuario_lab, os_base, db_session):
    _modelo(db_session, os_base["equipamento"])
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.post(f"/equipamentos-cliente/{os_base['equipamento_cliente']}/certificado-venda",
                    json=_payload(), headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["calib_cert"] == "V-001"

    from app.models import CertificadoVenda, EquipamentoCliente
    cv = db_session.query(CertificadoVenda).filter(
        CertificadoVenda.equipamento_cliente == os_base["equipamento_cliente"]).first()
    assert "Cliente OS" in cv.html and "SER-1" in cv.html and "XXXX" in cv.html
    assert "[" not in cv.html                     # nenhum token vazou
    assert cv.usuario == usuario_lab.id
    assert cv.data_geracao is not None

    ec = db_session.get(EquipamentoCliente, os_base["equipamento_cliente"])
    db_session.refresh(ec)
    assert ec.calib_cert == "V-001"
    assert ec.ult_calibragem == date(2026, 7, 20)
    assert ec.prox_calibragem == date(2027, 7, 20)


def test_regerar_sobrescreve_e_nao_duplica(client, usuario_lab, os_base, db_session):
    _modelo(db_session, os_base["equipamento"])
    h = _headers(client, "lab@hs.com", "senha123")
    url = f"/equipamentos-cliente/{os_base['equipamento_cliente']}/certificado-venda"
    assert client.post(url, json=_payload(), headers=h).status_code == 201
    r = client.post(url, json=_payload(calib_cert="V-002"), headers=h)
    assert r.status_code == 201

    from app.models import CertificadoVenda
    todos = db_session.query(CertificadoVenda).filter(
        CertificadoVenda.equipamento_cliente == os_base["equipamento_cliente"]).all()
    assert len(todos) == 1
    db_session.refresh(todos[0])
    assert todos[0].calib_cert == "V-002"


def test_aparelho_sem_modelo_de_certificado_409(client, usuario_lab, os_base):
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.post(f"/equipamentos-cliente/{os_base['equipamento_cliente']}/certificado-venda",
                    json=_payload(), headers=h)
    assert r.status_code == 409
    assert "modelo de certificado" in r.json()["detail"]


def test_admin_pode_gerar(client, usuario_admin, os_base, db_session):
    _modelo(db_session, os_base["equipamento"])
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.post(f"/equipamentos-cliente/{os_base['equipamento_cliente']}/certificado-venda",
                    json=_payload(), headers=h)
    assert r.status_code == 201


def test_comercial_nao_pode_gerar(client, usuario_comercial, os_base, db_session):
    _modelo(db_session, os_base["equipamento"])
    h = _headers(client, "comercial@hs.com", "senha123")
    r = client.post(f"/equipamentos-cliente/{os_base['equipamento_cliente']}/certificado-venda",
                    json=_payload(), headers=h)
    assert r.status_code == 403


def test_aparelho_inexistente_404(client, usuario_lab):
    h = _headers(client, "lab@hs.com", "senha123")
    assert client.get("/equipamentos-cliente/99999/certificado-venda-campos", headers=h).status_code == 404
    assert client.post("/equipamentos-cliente/99999/certificado-venda", json=_payload(), headers=h).status_code == 404


def test_pdf_baixa_e_404_sem_certificado(client, usuario_lab, os_base, db_session, monkeypatch):
    # Mesmo padrao do teste do avulso: a renderizacao real de PDF nao roda no ambiente
    # de teste, entao o que se verifica aqui e o roteamento e o content-type.
    from app.api import certificados_venda
    monkeypatch.setattr(certificados_venda, "html_para_pdf", lambda html: b"%PDF-fake")
    h = _headers(client, "lab@hs.com", "senha123")
    url = f"/equipamentos-cliente/{os_base['equipamento_cliente']}/certificado-venda/pdf"
    assert client.get(url, headers=h).status_code == 404
    _modelo(db_session, os_base["equipamento"])
    client.post(f"/equipamentos-cliente/{os_base['equipamento_cliente']}/certificado-venda",
                json=_payload(), headers=h)
    r = client.get(url, headers=h)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


def test_gerar_nao_cria_nem_altera_nenhuma_os(client, usuario_lab, os_base, db_session):
    """O ponto da feature: certificado de venda existe SEM OS."""
    _modelo(db_session, os_base["equipamento"])
    h = _headers(client, "lab@hs.com", "senha123")
    client.post(f"/equipamentos-cliente/{os_base['equipamento_cliente']}/certificado-venda",
                json=_payload(), headers=h)
    from app.models import Ordem, EquipamentoCliente
    assert db_session.query(Ordem).count() == 0
    ec = db_session.get(EquipamentoCliente, os_base["equipamento_cliente"])
    assert ec.os_atual is None
