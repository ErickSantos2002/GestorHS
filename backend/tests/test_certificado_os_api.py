def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _seed_fase5_se_necessario(db_session):
    from app.models import Fase, Funcao
    if db_session.query(Fase).filter(Fase.id == 5).first() is None:
        f = db_session.query(Funcao).filter(Funcao.descricao == "Laboratório").first()
        if f is None:
            f = Funcao(descricao="Laboratório")
            db_session.add(f); db_session.flush()
        db_session.add(Fase(id=5, descricao="Laboratório", cor="6366f1", funcao_responsavel=f.id))
        db_session.flush()


def _os_com_modelo(client, db_session, hadmin, tipos=("C",), tipo_servico="C"):
    from app.models import Cliente, Equipamento, EquipamentoCliente, Ordem, CertificadoModelo
    _seed_fase5_se_necessario(db_session)
    cat = Equipamento(descricao="Mark X"); db_session.add(cat); db_session.flush()
    cli = Cliente(nome="ACME"); db_session.add(cli); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=cat.id, serie="S1"); db_session.add(ec); db_session.flush()
    o = Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=5, situacao="E",
              tipo_servico=tipo_servico, calib_cert="C-1", calib_temp="25")
    db_session.add(o)
    for t in tipos:
        db_session.add(CertificadoModelo(equipamento=cat.id, tipo=t, texto=f"<p>[nomecli]-[serie]-{t}</p>"))
    db_session.commit(); db_session.refresh(o)
    return o.id


def test_gerar_calibracao(client, usuario_admin, db_session):
    h = _headers(client, "admin@hs.com", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")
    r = client.post(f"/ordens/{oid}/gerar-certificado", headers=h)
    assert r.status_code == 200
    tipos = {c["tipo"]: c for c in r.json()}
    assert "C" in tipos
    assert "ACME-S1-C" in tipos["C"]["html"]
    lista = client.get(f"/ordens/{oid}/certificados", headers=h).json()
    assert any(c["tipo"] == "C" for c in lista)


def test_gerar_manutencao_quando_servico_A(client, usuario_admin, db_session):
    h = _headers(client, "admin@hs.com", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C", "M"), tipo_servico="A")
    r = client.post(f"/ordens/{oid}/gerar-certificado", headers=h).json()
    assert {c["tipo"] for c in r} == {"C", "M"}


def test_nao_gera_manutencao_quando_servico_C(client, usuario_admin, db_session):
    h = _headers(client, "admin@hs.com", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C", "M"), tipo_servico="C")
    r = client.post(f"/ordens/{oid}/gerar-certificado", headers=h).json()
    assert {c["tipo"] for c in r} == {"C"}


def test_sem_modelo_recusa_com_aviso(client, usuario_admin, db_session):
    """Aparelho sem modelo cadastrado: recusa com 409 e mensagem clara.

    Antes este teste esperava 200 — ou seja, cristalizava a falha silenciosa: o endpoint
    nao gerava nada e mesmo assim respondia sucesso, e o usuario ficava sem saber por que
    o certificado nao aparecia.
    """
    from app.models import Cliente, Equipamento, EquipamentoCliente, Ordem
    h = _headers(client, "admin@hs.com", "senha123")
    _seed_fase5_se_necessario(db_session)
    cat = Equipamento(descricao="X"); db_session.add(cat); db_session.flush()
    cli = Cliente(nome="C"); db_session.add(cli); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=cat.id); db_session.add(ec); db_session.flush()
    o = Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=5, situacao="E", tipo_servico="C")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    r = client.post(f"/ordens/{o.id}/gerar-certificado", headers=h)
    assert r.status_code == 409
    assert "modelo" in r.json()["detail"].lower()


def test_regerar_atualiza_nao_duplica(client, usuario_admin, db_session):
    h = _headers(client, "admin@hs.com", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")
    client.post(f"/ordens/{oid}/gerar-certificado", headers=h)
    client.post(f"/ordens/{oid}/gerar-certificado", headers=h)
    lista = client.get(f"/ordens/{oid}/certificados", headers=h).json()
    assert len([c for c in lista if c["tipo"] == "C"]) == 1


def test_gerar_exige_lab_ou_admin(client, usuario_admin, usuario_comercial, db_session):
    h = _headers(client, "comercial@hs.com", "senha123")
    oid = _os_com_modelo(client, db_session, _headers(client, "admin@hs.com", "senha123"), tipos=("C",))
    assert client.post(f"/ordens/{oid}/gerar-certificado", headers=h).status_code == 403


def test_gerar_os_inexistente_404(client, usuario_admin):
    h = _headers(client, "admin@hs.com", "senha123")
    assert client.post("/ordens/99999/gerar-certificado", headers=h).status_code == 404


def test_gerar_com_dados_salva_e_preenche(client, usuario_admin, db_session):
    h = _headers(client, "admin@hs.com", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")
    body = {
        "calib_cert": "CERT-9", "calib_temp": "25",
        "calib_pressao": "1013", "calib_teste1": "0,10", "calib_teste2": "0,20",
        "calib_teste3": "0,30", "calib_teste_media": "0,20", "calib_situacao": "Aprovado",
    }
    r = client.post(f"/ordens/{oid}/gerar-certificado", json=body, headers=h)
    assert r.status_code == 200
    from app.models import Ordem
    o = db_session.get(Ordem, oid); db_session.refresh(o)
    assert o.calib_cert == "CERT-9" and o.calib_temp == "25"
    assert o.calib_situacao == "Aprovado"
    assert o.data_calibracao is not None
    assert any(c["tipo"] == "C" and c["html"] for c in r.json())


def test_gerar_sem_corpo_regenera_sem_alterar(client, usuario_admin, db_session):
    h = _headers(client, "admin@hs.com", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")
    client.post(f"/ordens/{oid}/gerar-certificado", json={"calib_cert": "X1"}, headers=h)
    from app.models import Ordem
    r = client.post(f"/ordens/{oid}/gerar-certificado", headers=h)
    assert r.status_code == 200
    o = db_session.get(Ordem, oid); db_session.refresh(o)
    assert o.calib_cert == "X1"


def test_baixar_pdf_sucesso(client, usuario_admin, db_session, monkeypatch):
    import app.api.certificados_os as mod
    monkeypatch.setattr(mod, "html_para_pdf", lambda html: b"%PDF-1.4 fake")
    h = _headers(client, "admin@hs.com", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")
    assert client.post(f"/ordens/{oid}/gerar-certificado", headers=h).status_code == 200
    r = client.get(f"/ordens/{oid}/certificado/C/pdf", headers=h)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "attachment" in r.headers["content-disposition"]
    assert r.content == b"%PDF-1.4 fake"


def test_baixar_pdf_sem_certificado_404(client, usuario_admin, db_session, monkeypatch):
    import app.api.certificados_os as mod
    monkeypatch.setattr(mod, "html_para_pdf", lambda html: b"%PDF")
    h = _headers(client, "admin@hs.com", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")
    # sem gerar certificado
    assert client.get(f"/ordens/{oid}/certificado/C/pdf", headers=h).status_code == 404


def test_gerar_grava_data_calibracao_informada(client, usuario_admin, db_session):
    h = _headers(client, "admin@hs.com", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")
    r = client.post(f"/ordens/{oid}/gerar-certificado", json={"calib_cert": "C1", "data_calibracao": "2026-01-15"}, headers=h)
    assert r.status_code == 200
    from app.models import Ordem
    o = db_session.get(Ordem, oid); db_session.refresh(o)
    assert o.data_calibracao is not None
    assert o.data_calibracao.date().isoformat() == "2026-01-15"


def test_regerar_sem_data_preserva_a_existente(client, usuario_admin, db_session):
    h = _headers(client, "admin@hs.com", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")
    client.post(f"/ordens/{oid}/gerar-certificado", json={"calib_cert": "C1", "data_calibracao": "2026-01-15"}, headers=h)
    r = client.post(f"/ordens/{oid}/gerar-certificado", json={"calib_cert": "C2"}, headers=h)
    assert r.status_code == 200
    from app.models import Ordem
    o = db_session.get(Ordem, oid); db_session.refresh(o)
    assert o.calib_cert == "C2"
    assert o.data_calibracao.date().isoformat() == "2026-01-15"


def test_certificado_campos_deriva_e_aplica_override(client, usuario_admin, db_session):
    h = _headers(client, "admin@hs.com", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")
    r = client.get(f"/ordens/{oid}/certificado-campos", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["nomecli"] == "ACME"
    assert body["serie"] == "S1"
    client.post(f"/ordens/{oid}/gerar-certificado", json={"nomecli": "NOME ESPECIAL"}, headers=h)
    body2 = client.get(f"/ordens/{oid}/certificado-campos", headers=h).json()
    assert body2["nomecli"] == "NOME ESPECIAL"


def test_gerar_grava_overrides_sem_alterar_cliente(client, usuario_admin, db_session):
    h = _headers(client, "admin@hs.com", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")
    r = client.post(f"/ordens/{oid}/gerar-certificado", json={"nomecli": "OUTRO NOME", "cnpj": "123"}, headers=h)
    assert r.status_code == 200
    from app.models import Ordem, Cliente
    o = db_session.get(Ordem, oid); db_session.refresh(o)
    assert o.cert_overrides == {"nomecli": "OUTRO NOME", "cnpj": "123"}
    assert "OUTRO NOME" in r.json()[0]["html"]
    cli = db_session.get(Cliente, o.cliente)
    assert cli.nome == "ACME"


def test_certificado_campos_404(client, usuario_admin):
    h = _headers(client, "admin@hs.com", "senha123")
    assert client.get("/ordens/99999/certificado-campos", headers=h).status_code == 404


def test_gerar_certificado_conclui_lab(client, usuario_admin, db_session):
    h = _headers(client, "admin@hs.com", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")
    r = client.post(f"/ordens/{oid}/gerar-certificado", headers=h)
    assert r.status_code == 200
    from app.models import Ordem, EquipamentoCliente
    o = db_session.get(Ordem, oid); db_session.refresh(o)
    assert o.desfecho_lab == "concluido"          # OS pronta para a caixa avançar
    ec = db_session.get(EquipamentoCliente, o.equipamento_cliente)
    assert ec.calib_cert == "C-1"                 # espelhado na frota


def test_gerar_nao_reabre_sem_conserto(client, usuario_admin, db_session):
    h = _headers(client, "admin@hs.com", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")
    from app.models import Ordem
    o = db_session.get(Ordem, oid); o.desfecho_lab = "sem_conserto"
    db_session.commit()
    r = client.post(f"/ordens/{oid}/gerar-certificado", headers=h)
    assert r.status_code == 200
    db_session.refresh(o)
    assert o.desfecho_lab == "sem_conserto"       # guarda `== pendente` não sobrescreve


def test_gerar_fora_do_lab_nao_conclui(client, usuario_admin, db_session):
    h = _headers(client, "admin@hs.com", "senha123")
    oid = _os_com_modelo(client, db_session, h, tipos=("C",), tipo_servico="C")
    from app.models import Ordem, Fase
    if db_session.query(Fase).filter(Fase.id == 8).first() is None:
        db_session.add(Fase(id=8, descricao="Finalizada", cor="10b981")); db_session.flush()
    o = db_session.get(Ordem, oid); o.fase = 8   # já passou do laboratório
    db_session.commit()
    r = client.post(f"/ordens/{oid}/gerar-certificado", headers=h)
    assert r.status_code == 200
    db_session.refresh(o)
    assert o.desfecho_lab == "pendente"           # guarda de fase bloqueia
