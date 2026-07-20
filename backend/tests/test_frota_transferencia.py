def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _cliente(db_session, nome):
    from app.models import Cliente
    c = Cliente(nome=nome)
    db_session.add(c); db_session.commit(); db_session.refresh(c)
    return c.id


def _ordem(db_session, cliente, equipamento_cliente, fase):
    from app.models import Ordem
    o = Ordem(cliente=cliente, equipamento_cliente=equipamento_cliente, fase=fase, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    return o.id


def test_transferir_muda_dono_zera_os_atual_e_registra(
    client, usuario_admin, os_base, db_session
):
    from app.models import EquipamentoCliente
    ec = db_session.get(EquipamentoCliente, os_base["equipamento_cliente"])
    ec.os_atual = 12345
    db_session.commit()
    destino = _cliente(db_session, "Empresa Nova")
    h = _headers(client, "admin@hs.com", "senha123")

    r = client.post(f"/equipamentos-cliente/{os_base['equipamento_cliente']}/transferir",
                    json={"cliente": destino, "obs": "venda"}, headers=h)
    assert r.status_code == 200
    assert r.json()["cliente"] == destino

    db_session.refresh(ec)
    assert ec.cliente == destino
    assert ec.os_atual is None

    trs = client.get(f"/equipamentos-cliente/{os_base['equipamento_cliente']}/transferencias", headers=h).json()
    assert len(trs) == 1
    assert trs[0]["de_cliente"] == os_base["cliente"]
    assert trs[0]["para_cliente"] == destino
    assert trs[0]["para_cliente_nome"] == "Empresa Nova"
    assert trs[0]["usuario_nome"] == "Admin"
    assert trs[0]["obs"] == "venda"


def test_transferir_bloqueia_com_os_ativa_409(client, usuario_admin, fases_seed, os_base, db_session):
    destino = _cliente(db_session, "Destino")
    _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 5)  # ativa
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.post(f"/equipamentos-cliente/{os_base['equipamento_cliente']}/transferir",
                    json={"cliente": destino}, headers=h)
    assert r.status_code == 409


def test_transferir_destino_inexistente_404(client, usuario_admin, os_base):
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.post(f"/equipamentos-cliente/{os_base['equipamento_cliente']}/transferir",
                    json={"cliente": 99999}, headers=h)
    assert r.status_code == 404


def test_transferir_mesmo_cliente_400(client, usuario_admin, os_base):
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.post(f"/equipamentos-cliente/{os_base['equipamento_cliente']}/transferir",
                    json={"cliente": os_base["cliente"]}, headers=h)
    assert r.status_code == 400


def test_transferir_liberado_para_laboratorio(client, usuario_lab, os_base, db_session):
    """O Laboratorio passou a poder transferir (20/07/2026): e' quem tem o aparelho
    na mao. EXCLUIR continua so com Administrador — ver o teste abaixo."""
    destino = _cliente(db_session, "Destino")
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.post(f"/equipamentos-cliente/{os_base['equipamento_cliente']}/transferir",
                    json={"cliente": destino}, headers=h)
    assert r.status_code == 200


def test_transferir_barra_funcao_sem_permissao_403(client, usuario_financeiro, os_base, db_session):
    """Liberar o Laboratorio nao pode virar liberar geral."""
    destino = _cliente(db_session, "Destino")
    h = _headers(client, "fin@hs.com", "senha123")
    r = client.post(f"/equipamentos-cliente/{os_base['equipamento_cliente']}/transferir",
                    json={"cliente": destino}, headers=h)
    assert r.status_code == 403


def test_excluir_aparelho_continua_so_admin_403(client, usuario_lab, os_base):
    """A acao destrutiva NAO foi liberada junto com cadastrar/alterar/transferir."""
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.delete(f"/equipamentos-cliente/{os_base['equipamento_cliente']}", headers=h)
    assert r.status_code == 403


def test_os_antiga_mantem_cliente_antigo(client, usuario_admin, fases_seed, os_base, db_session):
    from app.models import Ordem
    oid = _ordem(db_session, os_base["cliente"], os_base["equipamento_cliente"], 8)  # finalizada
    destino = _cliente(db_session, "Empresa Nova")
    h = _headers(client, "admin@hs.com", "senha123")
    client.post(f"/equipamentos-cliente/{os_base['equipamento_cliente']}/transferir",
                json={"cliente": destino}, headers=h)
    db_session.expire_all()
    assert db_session.get(Ordem, oid).cliente == os_base["cliente"]  # OS antiga: dono antigo
