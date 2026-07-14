def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _abrir_os(db_session):
    from app.models import Cliente, Equipamento, EquipamentoCliente, Ordem, Fase, Funcao
    funcao = db_session.query(Funcao).filter(Funcao.descricao == "Expedição").first()
    if funcao is None:
        funcao = Funcao(descricao="Expedição")
        db_session.add(funcao); db_session.flush()
    fase = db_session.query(Fase).filter(Fase.id == 4).first()
    if fase is None:
        fase = Fase(id=4, descricao="Recebido", cor="3b82f6", funcao_responsavel=funcao.id)
        db_session.add(fase); db_session.flush()
    cli = Cliente(nome="Cliente Foto")
    eq = Equipamento(descricao="Bafômetro")
    db_session.add_all([cli, eq]); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="S1")
    db_session.add(ec); db_session.flush()
    o = Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=4)
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    return o.id


def _img():
    return {"file": ("foto.jpg", b"\xff\xd8\xff_bytes", "image/jpeg")}


def test_upload_listar_servir_excluir(client, usuario_comum, upload_tmp, db_session):
    h = _headers(client, "comum@hs.com", "senha123")   # comum = Expedição (autorizado)
    os_id = _abrir_os(db_session)

    r = client.post(f"/ordens/{os_id}/fotos", files=_img(), data={"legenda": "frente"}, headers=h)
    assert r.status_code == 201
    foto = r.json()
    assert foto["os"] == os_id and foto["legenda"] == "frente" and foto["url"].endswith("/arquivo")

    lst = client.get(f"/ordens/{os_id}/fotos", headers=h).json()
    assert len(lst) == 1 and lst[0]["id"] == foto["id"]

    arq = client.get(foto["url"], headers=h)
    assert arq.status_code == 200 and arq.content == b"\xff\xd8\xff_bytes"

    assert client.delete(f"/fotos/{foto['id']}", headers=h).status_code == 204
    assert client.get(f"/ordens/{os_id}/fotos", headers=h).json() == []


def test_upload_tipo_invalido(client, usuario_comum, upload_tmp, db_session):
    h = _headers(client, "comum@hs.com", "senha123")
    os_id = _abrir_os(db_session)
    r = client.post(f"/ordens/{os_id}/fotos", files={"file": ("a.txt", b"x", "text/plain")}, headers=h)
    assert r.status_code == 415


def test_upload_404_os(client, usuario_comum, upload_tmp, db_session):
    h = _headers(client, "comum@hs.com", "senha123")
    assert client.post("/ordens/999999/fotos", files=_img(), headers=h).status_code == 404


def test_upload_403_nao_autorizado(client, usuario_lab, upload_tmp, db_session):
    h = _headers(client, "lab@hs.com", "senha123")  # Laboratório não pode subir foto de recebimento
    os_id = _abrir_os(db_session)
    assert client.post(f"/ordens/{os_id}/fotos", files=_img(), headers=h).status_code == 403


def test_excluir_403_nao_autorizado(client, usuario_comum, usuario_lab, upload_tmp, db_session):
    # cria a foto como Expedição (comum), tenta excluir como Laboratório (lab) -> 403
    hcom = _headers(client, "comum@hs.com", "senha123")
    os_id = _abrir_os(db_session)
    foto = client.post(f"/ordens/{os_id}/fotos", files=_img(), headers=hcom).json()
    hlab = _headers(client, "lab@hs.com", "senha123")
    assert client.delete(f"/fotos/{foto['id']}", headers=hlab).status_code == 403


def test_upload_413_acima_do_limite(client, usuario_comum, upload_tmp, db_session):
    h = _headers(client, "comum@hs.com", "senha123")
    os_id = _abrir_os(db_session)
    grande = b"x" * (10 * 1024 * 1024 + 1)
    r = client.post(f"/ordens/{os_id}/fotos", files={"file": ("g.jpg", grande, "image/jpeg")}, headers=h)
    assert r.status_code == 413


def test_baixar_foto_de_outra_os_404(client, usuario_comum, upload_tmp, db_session):
    h = _headers(client, "comum@hs.com", "senha123")
    os_a = _abrir_os(db_session)
    os_b = _abrir_os(db_session)
    foto = client.post(f"/ordens/{os_a}/fotos", files=_img(), headers=h).json()
    # pede o arquivo da foto de os_a usando o id de os_b na URL -> 404
    assert client.get(f"/ordens/{os_b}/fotos/{foto['id']}/arquivo", headers=h).status_code == 404


def test_baixar_foto_exige_auth(client, usuario_comum, upload_tmp, db_session):
    h = _headers(client, "comum@hs.com", "senha123")
    os_id = _abrir_os(db_session)
    foto = client.post(f"/ordens/{os_id}/fotos", files=_img(), headers=h).json()
    # sem header de autorização -> 401
    assert client.get(foto["url"]).status_code == 401
