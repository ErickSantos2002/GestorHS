def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_equipamentos_read_interno_write_admin(client, usuario_admin, usuario_comum):
    assert client.get("/equipamentos", headers=_headers(client, "comum", "senha123")).status_code == 200
    assert client.post("/equipamentos", json={"descricao": "X"}, headers=_headers(client, "comum", "senha123")).status_code == 403


def test_equipamento_crud_com_fks(client, usuario_admin, db_session):
    from app.models import Marca, Categoria
    m = Marca(descricao="Dräger")
    c = Categoria(descricao="Bafômetros", posicao=0)
    db_session.add_all([m, c])
    db_session.commit()
    h = _headers(client, "admin", "senha123")
    corpo = {"descricao": "Alcotest 6820", "categoria": c.id, "marca": m.id, "preco_por": 1500.50, "estoque": 3, "ativo": True}
    criado = client.post("/equipamentos", json=corpo, headers=h)
    assert criado.status_code == 201
    eid = criado.json()["id"]
    assert criado.json()["marca"] == m.id and criado.json()["ativo"] is True
    assert float(criado.json()["preco_por"]) == 1500.50
    assert client.patch(f"/equipamentos/{eid}", json={"estoque": 5}, headers=h).json()["estoque"] == 5
    assert client.delete(f"/equipamentos/{eid}", headers=h).status_code == 204


def test_excluir_marca_em_uso_409(client, usuario_admin, db_session):
    from app.models import Marca, Equipamento
    m = Marca(descricao="Em uso")
    db_session.add(m)
    db_session.flush()
    db_session.add(Equipamento(descricao="Eq", marca=m.id))
    db_session.commit()
    r = client.delete(f"/marcas/{m.id}", headers=_headers(client, "admin", "senha123"))
    assert r.status_code == 409


def test_excluir_categoria_em_uso_409(client, usuario_admin, db_session):
    from app.models import Categoria, Equipamento
    c = Categoria(descricao="Em uso", posicao=0)
    db_session.add(c)
    db_session.flush()
    db_session.add(Equipamento(descricao="Eq", categoria=c.id))
    db_session.commit()
    r = client.delete(f"/categorias/{c.id}", headers=_headers(client, "admin", "senha123"))
    assert r.status_code == 409
