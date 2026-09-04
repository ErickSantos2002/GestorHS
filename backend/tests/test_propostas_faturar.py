"""Testes do fluxo faturar/desfaturar de Proposta (Financeiro e Admin fazem os dois)."""


def _criar_proposta(client_comercial):
    r = client_comercial.post("/propostas", json={"itens": []})
    assert r.status_code == 201
    return r.json()["id"]


def test_financeiro_fatura_proposta(client_comercial, client_fin, db_session):
    pid = _criar_proposta(client_comercial)

    r = client_fin.post(f"/propostas/{pid}/faturar")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["faturada"] is True
    assert corpo["faturada_por"] == "Fin"

    from app.models import Proposta
    p = db_session.query(Proposta).filter(Proposta.id == pid).first()
    assert p.faturada is True
    assert p.faturada_em is not None
    assert p.faturada_por == "Fin"


def test_comercial_nao_pode_faturar(client_comercial):
    pid = _criar_proposta(client_comercial)
    r = client_comercial.post(f"/propostas/{pid}/faturar")
    assert r.status_code == 403


def test_admin_desfatura_proposta(client_comercial, client_fin, client_admin, db_session):
    pid = _criar_proposta(client_comercial)
    assert client_fin.post(f"/propostas/{pid}/faturar").status_code == 200

    r = client_admin.post(f"/propostas/{pid}/desfaturar")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["faturada"] is False
    assert corpo["faturada_em"] is None
    assert corpo["faturada_por"] is None

    from app.models import Proposta
    p = db_session.query(Proposta).filter(Proposta.id == pid).first()
    assert p.faturada is False
    assert p.faturada_em is None
    assert p.faturada_por is None


def test_financeiro_pode_desfaturar(client_comercial, client_fin):
    """Desfazer era exclusivo do Administrador ate 04/09/2026. Quem marca o
    faturamento e' quem descobre o engano, entao desfaz tambem."""
    pid = _criar_proposta(client_comercial)
    assert client_fin.post(f"/propostas/{pid}/faturar").status_code == 200

    r = client_fin.post(f"/propostas/{pid}/desfaturar")
    assert r.status_code == 200
    assert r.json()["faturada"] is False


def test_comercial_nao_pode_desfaturar(client_comercial):
    """O gate afrouxou para o Financeiro, nao para todo mundo: o Comercial cria a
    proposta mas nao mexe no faturamento dela.

    So `client_comercial` na assinatura de proposito: as fixtures de client mutam
    o MESMO objeto, entao pedir `client_fin` junto trocaria a identidade e o teste
    passaria a exercitar o Financeiro. O gate barra antes de olhar o estado da
    proposta, entao nem precisa fatura-la.
    """
    pid = _criar_proposta(client_comercial)
    r = client_comercial.post(f"/propostas/{pid}/desfaturar")
    assert r.status_code == 403


def test_faturar_e_idempotente(client_comercial, client_fin):
    pid = _criar_proposta(client_comercial)

    r1 = client_fin.post(f"/propostas/{pid}/faturar")
    assert r1.status_code == 200
    primeira_data = r1.json()["faturada_em"]

    r2 = client_fin.post(f"/propostas/{pid}/faturar")
    assert r2.status_code == 200
    assert r2.json()["faturada"] is True
    # nao regrava a data ao repetir a acao numa proposta ja faturada
    assert r2.json()["faturada_em"] == primeira_data


def test_desfaturar_proposta_nao_faturada_e_no_op(client_comercial, client_admin):
    pid = _criar_proposta(client_comercial)

    r = client_admin.post(f"/propostas/{pid}/desfaturar")
    assert r.status_code == 200
    assert r.json()["faturada"] is False


def test_proposta_out_traz_faturada(client_comercial):
    pid = _criar_proposta(client_comercial)

    r = client_comercial.get(f"/propostas/{pid}")
    assert r.status_code == 200
    assert r.json()["faturada"] is False

    r_lista = client_comercial.get("/propostas")
    assert r_lista.status_code == 200
    assert r_lista.json()["items"][0]["faturada"] is False
