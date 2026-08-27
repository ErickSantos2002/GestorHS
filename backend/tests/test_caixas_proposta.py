"""Bloco da proposta na tela da caixa: `GET /caixas/{id}/proposta`.

A caixa guarda so o NUMERO da proposta (gravado pelo inbound do GrowthHS ao
marcar "Ganho"). Este endpoint resolve numero -> Proposta local e devolve o
mesmo `PropostaOut` da tela de Propostas. Quando nao ha numero, ou o numero e
de uma proposta que nao existe aqui (legado do CRM), a resposta e 404 e o
frontend simplesmente nao desenha o bloco.
"""
from datetime import date


def _logar(client, email):
    """`client_fin` e `client_comercial` sao o MESMO TestClient — a ultima fixture
    resolvida sobrescreve o header. Onde a funcao importa, troque de papel aqui."""
    tok = client.post("/auth/login", json={"email": email, "senha": "senha123"}).json()
    client.headers["Authorization"] = f"Bearer {tok['access_token']}"


def _caixa(db_session, *, numero_proposta=None):
    from app.models import Caixa
    cx = Caixa(data=date(2026, 8, 21), numero_proposta=numero_proposta)
    db_session.add(cx)
    db_session.commit()
    db_session.refresh(cx)
    return cx


def _proposta(client_comercial, db_session, *, cgc="01899414000167"):
    from app.models import Cliente
    cli = Cliente(nome="CONCREFER", cgc=cgc)
    db_session.add(cli)
    db_session.commit()
    db_session.refresh(cli)
    _logar(client_comercial, "comercial@hs.com")
    r = client_comercial.post("/propostas", json={
        "cliente": cli.id,
        "data": "2026-08-20",
        "itens": [{"descricao": "Calibracao", "quantidade": 2, "preco_un": 395}],
    })
    assert r.status_code == 201
    return r.json()


def test_caixa_sem_numero_de_proposta_devolve_404(client_fin, db_session):
    cx = _caixa(db_session)
    assert client_fin.get(f"/caixas/{cx.id}/proposta").status_code == 404


def test_numero_de_proposta_que_nao_existe_aqui_devolve_404(client_fin, db_session):
    """Os numeros do legado/GrowthHS nao casam com nenhuma proposta local."""
    cx = _caixa(db_session, numero_proposta=16511)
    assert client_fin.get(f"/caixas/{cx.id}/proposta").status_code == 404


def test_caixa_inexistente_devolve_404(client_fin):
    assert client_fin.get("/caixas/98765/proposta").status_code == 404


def test_devolve_a_proposta_com_cliente_documento_e_valor(client_fin, client_comercial, db_session):
    p = _proposta(client_comercial, db_session)
    cx = _caixa(db_session, numero_proposta=p["numero"])

    _logar(client_fin, "fin@hs.com")
    r = client_fin.get(f"/caixas/{cx.id}/proposta")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["id"] == p["id"]
    assert corpo["numero"] == p["numero"]
    assert corpo["data"] == "2026-08-20"
    assert corpo["cliente_nome"] == "CONCREFER"
    assert corpo["cliente_documento"] == "01899414000167"
    assert corpo["total"] == 790.0
    assert corpo["faturada"] is False


def test_reflete_o_faturamento_da_proposta(client_fin, client_comercial, db_session):
    p = _proposta(client_comercial, db_session)
    cx = _caixa(db_session, numero_proposta=p["numero"])
    _logar(client_fin, "fin@hs.com")
    assert client_fin.post(f"/propostas/{p['id']}/faturar").status_code == 200

    corpo = client_fin.get(f"/caixas/{cx.id}/proposta").json()
    assert corpo["faturada"] is True
    assert corpo["faturada_por"] == "Fin"


def test_proposta_desabilitada_aparece_com_a_marca(client_fin, client_comercial, db_session):
    """Desabilitada nao some do bloco: o Financeiro precisa VER que a proposta
    daquela caixa foi tirada de circulacao, em vez do bloco sumir sem explicacao."""
    p = _proposta(client_comercial, db_session)
    cx = _caixa(db_session, numero_proposta=p["numero"])
    _logar(client_comercial, "comercial@hs.com")
    assert client_comercial.post(f"/propostas/{p['id']}/desabilitar").status_code == 200

    _logar(client_fin, "fin@hs.com")
    r = client_fin.get(f"/caixas/{cx.id}/proposta")
    assert r.status_code == 200
    assert r.json()["is_deleted"] is True


def test_detalhe_da_caixa_expoe_o_numero_da_proposta(client_fin, db_session):
    cx = _caixa(db_session, numero_proposta=189)
    corpo = client_fin.get(f"/caixas/{cx.id}").json()
    assert corpo["numero_proposta"] == 189


def test_detalhe_da_caixa_sem_proposta_traz_numero_nulo(client_fin, db_session):
    cx = _caixa(db_session)
    assert client_fin.get(f"/caixas/{cx.id}").json()["numero_proposta"] is None
