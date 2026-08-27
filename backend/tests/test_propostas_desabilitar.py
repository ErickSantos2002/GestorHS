"""Desabilitar/reativar proposta — o que antes se chamava excluir.

A "exclusao" de proposta sempre foi soft (`is_deleted`), mas o nome mentia e nao
havia volta pela tela. Agora: qualquer um do grupo de escrita desabilita, so o
Administrador reativa, e proposta desabilitada aceita LEITURA mas recusa ESCRITA.
"""


def _logar(client, email):
    """`client_*` sao o MESMO TestClient — a ultima fixture resolvida sobrescreve
    o header. Onde a funcao importa, troque de papel aqui."""
    tok = client.post("/auth/login", json={"email": email, "senha": "senha123"}).json()
    client.headers["Authorization"] = f"Bearer {tok['access_token']}"


def _criar(client_comercial):
    _logar(client_comercial, "comercial@hs.com")
    r = client_comercial.post("/propostas", json={
        "itens": [{"descricao": "Calibracao", "quantidade": 1, "preco_un": 100}],
    })
    assert r.status_code == 201
    return r.json()["id"]


# --- desabilitar -----------------------------------------------------------

def test_comercial_desabilita_proposta(client_comercial, db_session):
    pid = _criar(client_comercial)

    r = client_comercial.post(f"/propostas/{pid}/desabilitar")
    assert r.status_code == 200
    assert r.json()["is_deleted"] is True
    assert r.json()["deleted_at"] is not None

    from app.models import Proposta
    p = db_session.query(Proposta).filter(Proposta.id == pid).first()
    assert p.is_deleted is True
    assert p.deleted_at is not None


def test_desabilitar_e_idempotente(client_comercial):
    pid = _criar(client_comercial)
    primeira = client_comercial.post(f"/propostas/{pid}/desabilitar").json()["deleted_at"]

    r = client_comercial.post(f"/propostas/{pid}/desabilitar")
    assert r.status_code == 200
    assert r.json()["deleted_at"] == primeira


def test_laboratorio_nao_desabilita(client_comercial, client_lab):
    pid = _criar(client_comercial)
    _logar(client_lab, "lab@hs.com")
    assert client_lab.post(f"/propostas/{pid}/desabilitar").status_code == 403


def test_delete_nao_existe_mais(client_comercial):
    pid = _criar(client_comercial)
    assert client_comercial.delete(f"/propostas/{pid}").status_code == 405


# --- reativar --------------------------------------------------------------

def test_admin_reativa(client_comercial, client_admin, db_session):
    pid = _criar(client_comercial)
    assert client_comercial.post(f"/propostas/{pid}/desabilitar").status_code == 200

    _logar(client_admin, "admin@hs.com")
    r = client_admin.post(f"/propostas/{pid}/reativar")
    assert r.status_code == 200
    assert r.json()["is_deleted"] is False
    assert r.json()["deleted_at"] is None

    from app.models import Proposta
    p = db_session.query(Proposta).filter(Proposta.id == pid).first()
    assert p.is_deleted is False
    assert p.deleted_at is None


def test_comercial_nao_reativa(client_comercial):
    pid = _criar(client_comercial)
    assert client_comercial.post(f"/propostas/{pid}/desabilitar").status_code == 200
    assert client_comercial.post(f"/propostas/{pid}/reativar").status_code == 403


def test_reativar_e_idempotente(client_comercial, client_admin):
    pid = _criar(client_comercial)
    _logar(client_admin, "admin@hs.com")
    r = client_admin.post(f"/propostas/{pid}/reativar")
    assert r.status_code == 200
    assert r.json()["is_deleted"] is False


# --- listagem --------------------------------------------------------------

def test_listagem_esconde_desabilitada_por_padrao(client_comercial):
    pid = _criar(client_comercial)
    assert client_comercial.post(f"/propostas/{pid}/desabilitar").status_code == 200

    corpo = client_comercial.get("/propostas").json()
    assert corpo["total"] == 0


def test_listagem_traz_desabilitada_com_a_flag(client_comercial):
    pid = _criar(client_comercial)
    assert client_comercial.post(f"/propostas/{pid}/desabilitar").status_code == 200

    corpo = client_comercial.get("/propostas", params={"incluir_desabilitadas": "true"}).json()
    assert corpo["total"] == 1
    assert corpo["items"][0]["id"] == pid
    assert corpo["items"][0]["is_deleted"] is True


# --- leitura passa, escrita nao -------------------------------------------

def test_leitura_de_desabilitada_continua_valendo(client_comercial):
    pid = _criar(client_comercial)
    assert client_comercial.post(f"/propostas/{pid}/desabilitar").status_code == 200

    r = client_comercial.get(f"/propostas/{pid}")
    assert r.status_code == 200
    assert r.json()["is_deleted"] is True
    assert client_comercial.get(f"/propostas/{pid}/versoes").status_code == 200


def test_editar_desabilitada_e_recusado(client_comercial):
    pid = _criar(client_comercial)
    assert client_comercial.post(f"/propostas/{pid}/desabilitar").status_code == 200

    r = client_comercial.put(f"/propostas/{pid}", json={"observacoes": "nova"})
    assert r.status_code == 409


def test_duplicar_desabilitada_e_recusado(client_comercial):
    pid = _criar(client_comercial)
    assert client_comercial.post(f"/propostas/{pid}/desabilitar").status_code == 200
    assert client_comercial.post(f"/propostas/{pid}/duplicar").status_code == 409


def test_faturar_desabilitada_e_recusado(client_comercial, client_fin):
    pid = _criar(client_comercial)
    assert client_comercial.post(f"/propostas/{pid}/desabilitar").status_code == 200

    _logar(client_fin, "fin@hs.com")
    assert client_fin.post(f"/propostas/{pid}/faturar").status_code == 409


def test_proposta_inexistente_continua_404(client_comercial):
    assert client_comercial.post("/propostas/9999/desabilitar").status_code == 404
    assert client_comercial.get("/propostas/9999").status_code == 404
