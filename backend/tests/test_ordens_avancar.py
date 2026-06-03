def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _abrir(client, h, equipamento_cliente):
    return client.post("/ordens", json={"equipamento_cliente": equipamento_cliente, "tipo_servico": "C"}, headers=h).json()


def test_cadeia_feliz_completa(client, usuario_admin, usuario_comum, usuario_lab, usuario_comercial, fases_seed, os_base, db_session):
    he = _headers(client, "comum", "senha123")       # Expedição
    hl = _headers(client, "lab", "senha123")          # Laboratório
    hc = _headers(client, "comercial", "senha123")    # Comercial
    o = _abrir(client, he, os_base["equipamento_cliente"])
    oid = o["id"]
    # 4 -> 5 (Expedição)
    r = client.post(f"/ordens/{oid}/avancar", json={"obs": "ao lab"}, headers=he)
    assert r.status_code == 200 and r.json()["fase"] == 5
    # 5 -> 6 (Laboratório) seta data_calibracao
    r = client.post(f"/ordens/{oid}/avancar", json={}, headers=hl)
    assert r.json()["fase"] == 6 and r.json()["data_calibracao"] is not None
    # 6 -> 7 (Comercial) seta aceite
    r = client.post(f"/ordens/{oid}/avancar", json={}, headers=hc)
    assert r.json()["fase"] == 7 and r.json()["aceite"] is True and r.json()["data_aceite"] is not None
    # 7 -> 8 (Expedição) exige cod_retorno, situacao=F
    r = client.post(f"/ordens/{oid}/avancar", json={"cod_retorno": "BR123"}, headers=he)
    assert r.json()["fase"] == 8 and r.json()["situacao"] == "F" and r.json()["cod_retorno"] == "BR123"
    # logs acumulados: abertura + 4 avanços = 5
    assert len(client.get(f"/ordens/{oid}/logs", headers=he).json()) == 5


def test_avancar_funcao_errada_403(client, usuario_comum, usuario_lab, fases_seed, os_base):
    he = _headers(client, "comum", "senha123")
    hl = _headers(client, "lab", "senha123")
    o = _abrir(client, he, os_base["equipamento_cliente"])   # fase 4 (Expedição)
    # Laboratório não pode avançar a fase 4
    assert client.post(f"/ordens/{o['id']}/avancar", json={}, headers=hl).status_code == 403


def test_admin_override_avanca_qualquer_fase(client, usuario_admin, usuario_comum, fases_seed, os_base):
    he = _headers(client, "comum", "senha123")
    ha = _headers(client, "admin", "senha123")
    o = _abrir(client, he, os_base["equipamento_cliente"])
    # admin avança 4->5 mesmo sendo Administrador (não Expedição)
    assert client.post(f"/ordens/{o['id']}/avancar", json={}, headers=ha).json()["fase"] == 5


def test_avancar_cod_retorno_obrigatorio_422(client, usuario_admin, fases_seed, os_base, db_session):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"], fase=7, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    ha = _headers(client, "admin", "senha123")
    r = client.post(f"/ordens/{o.id}/avancar", json={}, headers=ha)
    assert r.status_code == 422


def test_avancar_os_encerrada_409(client, usuario_admin, fases_seed, os_base, db_session):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"], fase=8, situacao="F")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    ha = _headers(client, "admin", "senha123")
    assert client.post(f"/ordens/{o.id}/avancar", json={}, headers=ha).status_code == 409


def test_avancar_os_inexistente_404(client, usuario_admin, fases_seed):
    ha = _headers(client, "admin", "senha123")
    assert client.post("/ordens/9999/avancar", json={}, headers=ha).status_code == 404


def test_avancar_lab_com_calibracao_espelha(client, usuario_lab, fases_seed, os_base, db_session):
    from app.models import Ordem, EquipamentoCliente
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"], fase=5, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    h = _headers(client, "lab", "senha123")
    r = client.post(f"/ordens/{o.id}/avancar", json={
        "calib_cert": "HF999", "calib_temp": "22.0", "calib_teste_media": "0,16",
        "calib_situacao": "Aprovado", "prox_calibragem": "2027-06-03",
    }, headers=h)
    assert r.status_code == 200
    assert r.json()["fase"] == 6
    assert r.json()["calib_cert"] == "HF999"
    assert r.json()["calib_situacao"] == "Aprovado"
    ec = db_session.get(EquipamentoCliente, os_base["equipamento_cliente"])
    db_session.refresh(ec)
    assert ec.calib_cert == "HF999"
    assert ec.calib_situacao == "Aprovado"
    assert str(ec.prox_calibragem) == "2027-06-03"
    assert ec.ult_calibragem is not None


def test_avancar_lab_manutencao_pura_nao_espelha(client, usuario_lab, fases_seed, os_base, db_session):
    from app.models import Ordem, EquipamentoCliente
    ec0 = db_session.get(EquipamentoCliente, os_base["equipamento_cliente"])
    ec0.calib_cert = "ORIG"
    db_session.commit()
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"], fase=5, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    h = _headers(client, "lab", "senha123")
    r = client.post(f"/ordens/{o.id}/avancar", json={"obs": "só manutenção"}, headers=h)
    assert r.status_code == 200 and r.json()["fase"] == 6
    ec = db_session.get(EquipamentoCliente, os_base["equipamento_cliente"])
    db_session.refresh(ec)
    assert ec.calib_cert == "ORIG"  # inalterado


def test_avancar_lab_sem_equipamento_nao_quebra(client, usuario_lab, fases_seed, os_base, db_session):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=None, fase=5, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    h = _headers(client, "lab", "senha123")
    r = client.post(f"/ordens/{o.id}/avancar", json={"calib_cert": "X"}, headers=h)
    assert r.status_code == 200 and r.json()["fase"] == 6


def test_calibracao_ignorada_fora_da_fase_lab(client, usuario_comum, fases_seed, os_base, db_session):
    # usuario_comum = Expedição (responsável pela fase 4); calib enviado em 4->5 deve ser ignorado
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"], fase=4, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    h = _headers(client, "comum", "senha123")
    r = client.post(f"/ordens/{o.id}/avancar", json={"calib_cert": "NAOAPLICA"}, headers=h)
    assert r.status_code == 200 and r.json()["fase"] == 5
    assert r.json()["calib_cert"] is None
