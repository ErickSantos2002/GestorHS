import pytest

from app.core.config import settings
from app.integrations import tiny_client
from app.models import Cliente, Empresa

CNPJ_CLIENTE = "08857492000148"
CNPJ_FILIAL = "36312056000552"


@pytest.fixture(autouse=True)
def integracao_ligada(monkeypatch):
    monkeypatch.setattr(settings, "TINY_TOKEN", "tok-123")


@pytest.fixture()
def agendados(monkeypatch):
    """Quem foi agendado, sem falar com o Tiny."""
    registro = {"clientes": [], "empresas": []}
    monkeypatch.setattr(tiny_client, "sincronizar_cliente",
                        lambda cid, **kw: registro["clientes"].append(cid))
    monkeypatch.setattr(tiny_client, "sincronizar_empresa",
                        lambda eid, **kw: registro["empresas"].append(eid))
    return registro


def _cliente(db, **kw):
    base = dict(nome="ACME", cgc=CNPJ_CLIENTE)
    base.update(kw)
    c = Cliente(**base); db.add(c); db.commit(); db.refresh(c)
    return c


def _dest(cliente_id):
    return {"tipo": "cliente", "id": cliente_id, "nome": "ACME"}


def test_criar_proposta_para_cliente_sem_tiny_agenda(client_comercial, agendados, db_session):
    c = _cliente(db_session)
    r = client_comercial.post("/propostas", json={"destinatario": _dest(c.id)})
    assert r.status_code == 201, r.text
    assert agendados["clientes"] == [c.id]
    db_session.refresh(c)
    assert c.tiny_status == "pendente" and c.tiny_erro is None


def test_cliente_com_tiny_id_nao_agenda_nem_marca(client_comercial, agendados, db_session):
    c = _cliente(db_session, tiny_id=610662219, tiny_status="enviada")
    r = client_comercial.post("/propostas", json={"destinatario": _dest(c.id)})
    assert r.status_code == 201
    assert agendados["clientes"] == []
    db_session.refresh(c)
    assert c.tiny_status == "enviada"


def test_editar_proposta_agenda(client_comercial, agendados, db_session):
    c = _cliente(db_session)
    pid = client_comercial.post("/propostas", json={"destinatario": _dest(c.id)}).json()["id"]
    agendados["clientes"].clear()
    r = client_comercial.put(f"/propostas/{pid}", json={"destinatario": _dest(c.id)})
    assert r.status_code == 200 and agendados["clientes"] == [c.id]


def test_editar_proposta_de_cliente_inativo_agenda(client_comercial, agendados, db_session):
    c = _cliente(db_session)
    pid = client_comercial.post("/propostas", json={"destinatario": _dest(c.id)}).json()["id"]
    c.ativo = False; db_session.commit()
    agendados["clientes"].clear()
    r = client_comercial.put(f"/propostas/{pid}", json={"destinatario": _dest(c.id)})
    assert r.status_code == 200 and agendados["clientes"] == [c.id]


def test_duplicar_proposta_agenda(client_comercial, agendados, db_session):
    c = _cliente(db_session)
    pid = client_comercial.post("/propostas", json={"destinatario": _dest(c.id)}).json()["id"]
    agendados["clientes"].clear()
    r = client_comercial.post(f"/propostas/{pid}/duplicar")
    assert r.status_code == 201 and agendados["clientes"] == [c.id]


def test_proposta_para_empresa_nao_agenda_a_matriz(client_comercial, agendados, db_session):
    """So o DESTINATARIO conta: a matriz de uma filial nao entra por tabela."""
    matriz = _cliente(db_session)
    emp = Empresa(nome="Filial", cgc=CNPJ_FILIAL, cliente=matriz.id)
    db_session.add(emp); db_session.commit()
    r = client_comercial.post("/propostas", json={"destinatario": {
        "tipo": "empresa", "id": emp.id, "matriz": matriz.id, "nome": "Filial"}})
    assert r.status_code == 201, r.text
    assert agendados["clientes"] == [] and agendados["empresas"] == [emp.id]


def test_integracao_desligada_nao_agenda_nem_marca(client_comercial, agendados, db_session, monkeypatch):
    monkeypatch.setattr(settings, "TINY_TOKEN", "")
    c = _cliente(db_session)
    assert client_comercial.post("/propostas", json={"destinatario": _dest(c.id)}).status_code == 201
    db_session.refresh(c)
    assert agendados["clientes"] == [] and c.tiny_status is None


def test_falha_do_tiny_nao_derruba_a_proposta(client_comercial, db_session, monkeypatch):
    def explode(*a, **k):
        raise RuntimeError("Tiny fora do ar")
    monkeypatch.setattr(tiny_client, "sincronizar_cliente", explode)
    c = _cliente(db_session)
    assert client_comercial.post("/propostas", json={"destinatario": _dest(c.id)}).status_code == 201


def test_falha_ao_marcar_pendente_nao_levanta():
    from types import SimpleNamespace
    from app.api.propostas import _agendar_cliente_no_tiny

    class BancoQuebrado:
        def get(self, *a, **k):
            raise RuntimeError("banco fora do ar")

        def rollback(self):
            pass

    tarefas = SimpleNamespace(add_task=lambda *a, **k: None)
    _agendar_cliente_no_tiny(BancoQuebrado(), tarefas,
                             SimpleNamespace(empresa=None, cliente=1))   # nao levanta
