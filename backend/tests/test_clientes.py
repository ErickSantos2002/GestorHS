def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_clientes_leitura_e_cadastro_por_funcao(client, usuario_admin, usuario_comum, usuario_financeiro):
    # Expedicao (usuario_comum) le e agora TAMBEM cadastra clientes
    exp = _headers(client, "comum@hs.com", "senha123")
    assert client.get("/clientes", headers=exp).status_code == 200
    assert client.post("/clientes", json={"nome": "X"}, headers=exp).status_code == 201
    # uma funcao sem cadastro (Financeiro) le mas nao cadastra
    fin = _headers(client, "fin@hs.com", "senha123")
    assert client.get("/clientes", headers=fin).status_code == 200
    assert client.post("/clientes", json={"nome": "Y"}, headers=fin).status_code == 403


def test_cliente_crud(client, usuario_admin):
    h = _headers(client, "admin@hs.com", "senha123")
    criado = client.post("/clientes", json={"nome": "ACME LTDA", "municipio": "São Paulo", "cgc": "11222333000144"}, headers=h)
    assert criado.status_code == 201
    cid = criado.json()["id"]
    assert client.get(f"/clientes/{cid}", headers=h).json()["nome"] == "ACME LTDA"
    assert client.get("/clientes/99999", headers=h).status_code == 404
    assert client.patch(f"/clientes/{cid}", json={"municipio": "Campinas"}, headers=h).json()["municipio"] == "Campinas"
    assert client.delete(f"/clientes/{cid}", headers=h).status_code == 204
    assert client.get(f"/clientes/{cid}", headers=h).status_code == 404


def test_clientes_busca_e_paginacao(client, usuario_admin, db_session):
    from app.models import Cliente
    for i in range(30):
        db_session.add(Cliente(nome=f"Cliente {i:02d}", municipio="Sorocaba"))
    db_session.add(Cliente(nome="Especial", municipio="Bauru"))
    db_session.commit()
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.get("/clientes?offset=0&limit=10", headers=h).json()
    assert r["total"] == 31
    assert len(r["items"]) == 10
    r2 = client.get("/clientes?q=Especial", headers=h).json()
    assert r2["total"] == 1
    assert r2["items"][0]["nome"] == "Especial"
    r3 = client.get("/clientes?q=Sorocaba", headers=h).json()
    assert r3["total"] == 30


def test_clientes_busca_por_documento_formatado(client, usuario_admin, db_session):
    from app.models import Cliente
    db_session.add(Cliente(nome="Doc Cliente", cgc="01899414000167"))
    db_session.add(Cliente(nome="Outro Cliente", cgc="99988877000166"))
    db_session.commit()
    h = _headers(client, "admin@hs.com", "senha123")

    # formatado (com pontuacao) deve encontrar o cliente pelo cgc digitos-apenas
    r_formatado = client.get("/clientes", headers=h, params={"q": "01.899.414/0001-67"}).json()
    assert r_formatado["total"] == 1
    assert r_formatado["items"][0]["nome"] == "Doc Cliente"

    # raw (so digitos) continua funcionando
    r_raw = client.get("/clientes", headers=h, params={"q": "01899414000167"}).json()
    assert r_raw["total"] == 1
    assert r_raw["items"][0]["nome"] == "Doc Cliente"

    # parcial formatado
    r_parcial = client.get("/clientes", headers=h, params={"q": "01.899"}).json()
    assert r_parcial["total"] == 1
    assert r_parcial["items"][0]["nome"] == "Doc Cliente"

    # busca por nome continua funcionando e nao vira match-all
    r_nome = client.get("/clientes", headers=h, params={"q": "Doc Cliente"}).json()
    assert r_nome["total"] == 1
    assert r_nome["items"][0]["nome"] == "Doc Cliente"


def test_excluir_cliente_em_uso_409(client, usuario_admin, db_session):
    from app.models import Cliente, Funcionario
    c = Cliente(nome="Com funcionario")
    db_session.add(c)
    db_session.flush()
    db_session.add(Funcionario(cliente=c.id, nome="João"))
    db_session.commit()
    r = client.delete(f"/clientes/{c.id}", headers=_headers(client, "admin@hs.com", "senha123"))
    assert r.status_code == 409


def test_pos_vendas_edita_cliente_mas_nao_cria(client, usuario_admin, usuario_comercial):
    """Pos-Vendas corrige endereco e demais dados do cliente, mas nao cadastra cliente novo."""
    adm = _headers(client, "admin@hs.com", "senha123")
    criado = client.post("/clientes", json={"nome": "ACME"}, headers=adm)
    assert criado.status_code == 201
    cid = criado.json()["id"]

    pv = _headers(client, "comercial@hs.com", "senha123")
    r = client.patch(f"/clientes/{cid}", json={"endereco": "Rua Nova", "municipio": "Campinas"}, headers=pv)
    assert r.status_code == 200
    assert r.json()["endereco"] == "Rua Nova"
    assert client.post("/clientes", json={"nome": "Outro"}, headers=pv).status_code == 403
    assert client.delete(f"/clientes/{cid}", headers=pv).status_code == 403


def test_gestores_continuam_editando_cliente(client, usuario_admin, usuario_comum):
    """Controle: quem ja editava (Expedicao) nao perdeu nada com a separacao das tuplas."""
    adm = _headers(client, "admin@hs.com", "senha123")
    cid = client.post("/clientes", json={"nome": "ACME 2"}, headers=adm).json()["id"]
    exp = _headers(client, "comum@hs.com", "senha123")
    assert client.patch(f"/clientes/{cid}", json={"bairro": "Centro"}, headers=exp).status_code == 200
