def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _os_do_cliente(db_session, cliente_id):
    from app.models import Equipamento, EquipamentoCliente, Ordem
    eq = Equipamento(descricao="Bafômetro"); db_session.add(eq); db_session.flush()
    ec = EquipamentoCliente(cliente=cliente_id, equipamento=eq.id, serie="S1"); db_session.add(ec); db_session.flush()
    o = Ordem(cliente=cliente_id, equipamento_cliente=ec.id)
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    return o.id


def _pdf():
    return {"file": ("cert.pdf", b"%PDF-1.4 fake", "application/pdf")}


def test_upload_e_download_interno(client, usuario_lab, upload_tmp, db_session):
    from app.models import Cliente
    cli = Cliente(nome="Cli"); db_session.add(cli); db_session.commit()
    os_id = _os_do_cliente(db_session, cli.id)
    h = _headers(client, "lab", "senha123")
    r = client.post(f"/ordens/{os_id}/certificado", files=_pdf(), headers=h)
    assert r.status_code == 200
    arq = client.get(f"/ordens/{os_id}/certificado", headers=h)
    assert arq.status_code == 200 and arq.content == b"%PDF-1.4 fake"


def test_upload_tipo_invalido(client, usuario_lab, upload_tmp, db_session):
    from app.models import Cliente
    cli = Cliente(nome="Cli"); db_session.add(cli); db_session.commit()
    os_id = _os_do_cliente(db_session, cli.id)
    h = _headers(client, "lab", "senha123")
    r = client.post(f"/ordens/{os_id}/certificado", files={"file": ("a.txt", b"x", "text/plain")}, headers=h)
    assert r.status_code == 415


def test_upload_403(client, usuario_comum, upload_tmp, db_session):
    from app.models import Cliente
    cli = Cliente(nome="Cli"); db_session.add(cli); db_session.commit()
    os_id = _os_do_cliente(db_session, cli.id)
    h = _headers(client, "comum", "senha123")
    assert client.post(f"/ordens/{os_id}/certificado", files=_pdf(), headers=h).status_code == 403


def test_upload_404_os(client, usuario_lab, upload_tmp, db_session):
    assert client.post("/ordens/999999/certificado", files=_pdf(), headers=_headers(client, "lab", "senha123")).status_code == 404


def test_download_sem_certificado_404(client, usuario_lab, upload_tmp, db_session):
    from app.models import Cliente
    cli = Cliente(nome="Cli"); db_session.add(cli); db_session.commit()
    os_id = _os_do_cliente(db_session, cli.id)
    assert client.get(f"/ordens/{os_id}/certificado", headers=_headers(client, "lab", "senha123")).status_code == 404


def test_download_url_legada_redireciona(client, usuario_lab, upload_tmp, db_session):
    from app.models import Cliente, Ordem
    cli = Cliente(nome="Cli"); db_session.add(cli); db_session.commit()
    os_id = _os_do_cliente(db_session, cli.id)
    o = db_session.query(Ordem).get(os_id); o.pdf_certificado = "http://exemplo/cert.pdf"; db_session.commit()
    r = client.get(f"/ordens/{os_id}/certificado", headers=_headers(client, "lab", "senha123"), follow_redirects=False)
    assert r.status_code in (302, 307)


def test_reenvio_substitui_arquivo(client, usuario_lab, upload_tmp, db_session):
    from app.models import Cliente, Ordem
    from app.core import storage
    cli = Cliente(nome="Cli"); db_session.add(cli); db_session.commit()
    os_id = _os_do_cliente(db_session, cli.id)
    h = _headers(client, "lab", "senha123")
    r1 = client.post(f"/ordens/{os_id}/certificado", files=_pdf(), headers=h)
    antigo = r1.json()["pdf_certificado"]
    # reenviar outro PDF
    r2 = client.post(f"/ordens/{os_id}/certificado", files={"file": ("novo.pdf", b"%PDF-1.4 novo", "application/pdf")}, headers=h)
    novo = r2.json()["pdf_certificado"]
    assert novo != antigo
    # o arquivo antigo foi removido do disco; o novo é servido
    assert not storage.caminho_arquivo(f"certificados/{os_id}", antigo).exists()
    arq = client.get(f"/ordens/{os_id}/certificado", headers=h)
    assert arq.content == b"%PDF-1.4 novo"
    # o registro aponta para o novo basename
    db_session.expire_all()
    assert db_session.query(Ordem).get(os_id).pdf_certificado == novo


def test_upload_413(client, usuario_lab, upload_tmp, db_session):
    from app.models import Cliente
    cli = Cliente(nome="Cli"); db_session.add(cli); db_session.commit()
    os_id = _os_do_cliente(db_session, cli.id)
    grande = b"x" * (10 * 1024 * 1024 + 1)
    r = client.post(f"/ordens/{os_id}/certificado", files={"file": ("g.pdf", grande, "application/pdf")}, headers=_headers(client, "lab", "senha123"))
    assert r.status_code == 413


def _portal_headers(client, db_session, cliente_id):
    from app.models import UsuarioCliente, Cliente
    from app.core.security import hash_senha
    empresa = db_session.query(Cliente).get(cliente_id)
    empresa.cgc = "11222333000144"
    uc = UsuarioCliente(cliente=cliente_id, nome="P", login="p1", senha=hash_senha("portal123"), precisa_redefinir_senha=False)
    db_session.add(uc); db_session.commit()
    tok = client.post("/auth/login-portal", json={"documento": "11222333000144", "login": "p1", "senha": "portal123"}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_portal_baixa_so_do_proprio_cliente(client, usuario_lab, upload_tmp, db_session):
    from app.models import Cliente
    dono = Cliente(nome="Dono"); outro = Cliente(nome="Outro"); db_session.add_all([dono, outro]); db_session.commit()
    os_id = _os_do_cliente(db_session, dono.id)
    client.post(f"/ordens/{os_id}/certificado", files=_pdf(), headers=_headers(client, "lab", "senha123"))
    h = _portal_headers(client, db_session, dono.id)
    assert client.get(f"/portal/certificados/{os_id}", headers=h).status_code == 200
    os_outro = _os_do_cliente(db_session, outro.id)
    # dá um certificado à OS do outro cliente: agora o 404 só pode vir do filtro de tenant
    client.post(f"/ordens/{os_outro}/certificado", files=_pdf(), headers=_headers(client, "lab", "senha123"))
    assert client.get(f"/portal/certificados/{os_outro}", headers=h).status_code == 404
