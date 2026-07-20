"""Saneamento da entrada do cadastro de cliente.

Nasceu de um 500 em producao: um paste deixou o CEP como ' 35530000' (9 chars)
e a coluna char(8) estourou no INSERT — `StringDataRightTruncation`.
"""


def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _criar(client, h, **campos):
    base = {"nome": "PH INTRALOGISTICA E SERVICOS LTDA"}
    base.update(campos)
    return client.post("/clientes", json=base, headers=h)


def test_cep_com_espaco_na_frente_nao_estoura_a_coluna(client, usuario_admin):
    """O caso exato que derrubou a request em producao."""
    h = _headers(client, "admin@hs.com", "senha123")
    r = _criar(client, h, cep=" 35530000", email=" junior.mariano@phintralog.com")
    assert r.status_code == 201
    assert r.json()["cep"] == "35530000"
    assert r.json()["email"] == "junior.mariano@phintralog.com"


def test_cep_e_documentos_perdem_a_mascara(client, usuario_admin):
    h = _headers(client, "admin@hs.com", "senha123")
    r = _criar(client, h, cep="35530-000", cgc="22.060.255/0001-82")
    assert r.status_code == 201
    assert r.json()["cep"] == "35530000"
    assert r.json()["cgc"] == "22060255000182"


def test_cpf_com_mascara(client, usuario_admin):
    h = _headers(client, "admin@hs.com", "senha123")
    r = _criar(client, h, cpf="123.456.789-01")
    assert r.status_code == 201
    assert r.json()["cpf"] == "12345678901"


def test_campo_vazio_vira_nulo_em_vez_de_string_vazia(client, usuario_admin):
    h = _headers(client, "admin@hs.com", "senha123")
    r = _criar(client, h, cep="", cgc="   ")
    assert r.status_code == 201
    assert r.json()["cep"] is None
    assert r.json()["cgc"] is None


def test_documento_longo_demais_da_422_e_nao_500(client, usuario_admin):
    """Recusar na entrada e melhor que estourar no INSERT (ou truncar calado)."""
    h = _headers(client, "admin@hs.com", "senha123")
    assert _criar(client, h, cep="355300001234").status_code == 422
    assert _criar(client, h, cgc="1" * 20).status_code == 422
    assert _criar(client, h, estado="Minas Gerais").status_code == 422


def test_patch_sofre_o_mesmo_saneamento(client, usuario_admin):
    h = _headers(client, "admin@hs.com", "senha123")
    cid = _criar(client, h).json()["id"]
    r = client.patch(f"/clientes/{cid}", json={"cep": " 35530-000 "}, headers=h)
    assert r.status_code == 200
    assert r.json()["cep"] == "35530000"
