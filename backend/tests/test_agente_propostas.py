"""Fase 2c do Guardi: Servicos (Comercial Pos-Vendas) e Financeiro criam e alteram
proposta pelo token de agente. O destinatario so VINCULA ao cadastro, nada agenda o
Tiny, e proposta faturada nao muda por aqui."""
import pytest

from app.core.config import settings
from app.integrations import tiny_client
from app.models import Cliente, Empresa, Proposta, PropostaVersao

MSG_DEST = "Pelo Guardi o destinatário só é escolhido ({tipo, id}): o cadastro não é alterado por aqui"


@pytest.fixture()
def como(client, fases_seed, agente):
    def _como(email):
        client.headers["Authorization"] = f"Bearer {agente(email)}"
        return client
    return _como


@pytest.fixture()
def tiny(monkeypatch):
    """Integracao ligada e espionada: o agente nao pode agendar nada."""
    monkeypatch.setattr(settings, "TINY_TOKEN", "tok-123")
    chamadas = []
    monkeypatch.setattr(tiny_client, "sincronizar_cliente", lambda cid, **kw: chamadas.append(("c", cid)))
    monkeypatch.setattr(tiny_client, "sincronizar_empresa", lambda eid, **kw: chamadas.append(("e", eid)))
    return chamadas


@pytest.fixture()
def cliente(db_session):
    c = Cliente(nome="ACME LTDA", cgc="08857492000148", endereco="Rua A", municipio="Recife", estado="PE")
    db_session.add(c); db_session.commit(); db_session.refresh(c)
    return c


@pytest.fixture()
def empresa(db_session, cliente):
    e = Empresa(nome="ACME FILIAL", cgc="36312056000552", cliente=cliente.id, municipio="Olinda", estado="PE")
    db_session.add(e); db_session.commit(); db_session.refresh(e)
    return e


def _corpo(dest=None, **kw):
    corpo = {"intro": "Prezados", "itens": [{"descricao": "Calibração", "quantidade": 2, "preco_un": 395}]}
    if dest is not None:
        corpo["destinatario"] = dest
    corpo.update(kw)
    return corpo


@pytest.mark.parametrize("usuario,email", [("usuario_comercial", "comercial@hs.com"),
                                           ("usuario_financeiro", "fin@hs.com")])
def test_cria_e_altera(como, request, cliente, db_session, tiny, usuario, email):
    request.getfixturevalue(usuario)
    c = como(email)
    r = c.post("/propostas", json=_corpo({"tipo": "cliente", "id": cliente.id}))
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["cliente"] == cliente.id and p["empresa"] is None
    assert p["destinatario"]["nome"] == "ACME LTDA"  # copia congelada do cadastro atual
    assert p["total_itens"] == 790
    r = c.put(f"/propostas/{p['id']}", json={"desconto": 40})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 750
    [v] = db_session.query(PropostaVersao).filter(PropostaVersao.proposta == p["id"]).all()
    assert v.alterado_por.endswith("via erick-bot")
    assert v.snapshot["total"] == 790  # arquivou o estado ANTERIOR
    assert tiny == []


def test_vinculo_a_empresa_traz_a_matriz(como, usuario_comercial, empresa, cliente, tiny):
    r = como("comercial@hs.com").post("/propostas", json=_corpo({"tipo": "empresa", "id": empresa.id}))
    assert r.status_code == 201, r.text
    assert (r.json()["empresa"], r.json()["cliente"]) == (empresa.id, cliente.id)
    assert tiny == []


@pytest.mark.parametrize("usuario,email", [("usuario_lab", "lab@hs.com"), ("usuario_comum", "comum@hs.com"),
                                           ("usuario_consulta", "consulta@hs.com")])
def test_outras_funcoes_403(como, request, cliente, db_session, usuario, email):
    request.getfixturevalue(usuario)
    p = Proposta(numero=500, cliente=cliente.id); db_session.add(p); db_session.commit()
    c = como(email)
    assert c.post("/propostas", json=_corpo({"tipo": "cliente", "id": cliente.id})).status_code == 403
    assert c.put(f"/propostas/{p.id}", json={"desconto": 1}).status_code == 403


@pytest.mark.parametrize("dest", [
    {"tipo": "cliente", "id": "CLI", "nome": "OUTRO NOME"},
    {"tipo": "cliente", "id": "CLI", "nome": "ACME LTDA", "endereco": "Rua Nova, 1"},
    {"tipo": "nova_empresa", "nome": "NOVA", "documento": "11222333000181"},
    {"tipo": "nova_empresa"},
])
def test_destinatario_com_dados_403_e_cadastro_intacto(como, usuario_comercial, cliente, db_session, tiny, dest):
    dest = {k: (cliente.id if v == "CLI" else v) for k, v in dest.items()}
    r = como("comercial@hs.com").post("/propostas", json=_corpo(dest))
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == MSG_DEST
    db_session.refresh(cliente)
    assert (cliente.nome, cliente.endereco) == ("ACME LTDA", "Rua A")
    assert db_session.query(Empresa).count() == 0
    assert db_session.query(Proposta).count() == 0
    assert tiny == []


def test_put_com_destinatario_403(como, usuario_comercial, cliente, db_session):
    p = Proposta(numero=501, cliente=cliente.id); db_session.add(p); db_session.commit()
    r = como("comercial@hs.com").put(f"/propostas/{p.id}", json={"destinatario": {"tipo": "cliente", "id": cliente.id}})
    assert r.status_code == 403
    assert db_session.query(PropostaVersao).count() == 0


def test_put_em_faturada_409(como, usuario_financeiro, cliente, db_session):
    p = Proposta(numero=502, cliente=cliente.id, faturada=True); db_session.add(p); db_session.commit()
    r = como("fin@hs.com").put(f"/propostas/{p.id}", json={"desconto": 10})
    assert r.status_code == 409
    db_session.refresh(p)
    assert float(p.desconto or 0) == 0


def test_cliente_inexistente_422_e_desativado_409(como, usuario_comercial, cliente, db_session):
    c = como("comercial@hs.com")
    assert c.post("/propostas", json=_corpo({"tipo": "cliente", "id": 99999})).status_code == 422
    cliente.ativo = False; db_session.commit()
    assert c.post("/propostas", json=_corpo({"tipo": "cliente", "id": cliente.id})).status_code == 409


def test_leituras_da_fase(como, usuario_comercial):
    c = como("comercial@hs.com")
    for caminho in ("/propostas/padrao", "/servicos", "/produtos"):
        assert c.get(caminho).status_code == 200, caminho


def test_tela_nao_aceita_so_tipo_e_id(client_comercial, cliente):
    r = client_comercial.post("/propostas", json=_corpo({"tipo": "cliente", "id": cliente.id}))
    assert r.status_code == 422


def test_tela_segue_igual_em_faturada(client_fin, cliente, db_session):
    p = Proposta(numero=503, cliente=cliente.id, faturada=True); db_session.add(p); db_session.commit()
    assert client_fin.put(f"/propostas/{p.id}", json={"desconto": 10}).status_code == 200
