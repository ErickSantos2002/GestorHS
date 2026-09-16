import pytest

from app.core.config import settings
from app.integrations import tiny_client
from app.models import Cliente, Empresa

CNPJ_A = "36312056000552"
CNPJ_B = "11222333000181"


@pytest.fixture(autouse=True)
def integracao_ligada(monkeypatch):
    monkeypatch.setattr(settings, "TINY_TOKEN", "tok-123")


@pytest.fixture()
def agendados(monkeypatch):
    """Registra quem foi agendado, sem falar com o Tiny."""
    ids = []
    monkeypatch.setattr(tiny_client, "sincronizar_empresa", lambda eid, **kw: ids.append(eid))
    import app.api.empresas as api_empresas
    monkeypatch.setattr(api_empresas.tiny_client, "sincronizar_empresa", lambda eid, **kw: ids.append(eid))
    return ids


def _payload(**kw):
    base = {"documento": CNPJ_A, "nome": "Filial Norte", "cliente": None}
    base.update(kw)
    return base


def test_criar_empresa_agenda_o_envio(client_comercial, agendados, db_session):
    r = client_comercial.post("/empresas", json=_payload())
    assert r.status_code == 201
    corpo = r.json()
    assert corpo["tiny_status"] == "pendente" and corpo["tiny_id"] is None
    assert agendados == [corpo["id"]]


def test_editar_empresa_agenda_o_envio(client_comercial, agendados):
    eid = client_comercial.post("/empresas", json=_payload()).json()["id"]
    agendados.clear()
    r = client_comercial.put(f"/empresas/{eid}", json=_payload(nome="Filial Sul"))
    assert r.status_code == 200 and agendados == [eid]


def test_desativar_nao_agenda(client_comercial, agendados):
    eid = client_comercial.post("/empresas", json=_payload()).json()["id"]
    agendados.clear()
    assert client_comercial.post(f"/empresas/{eid}/desativar").status_code == 200
    assert agendados == []


def test_integracao_desligada_nao_agenda_nem_marca(client_comercial, agendados, monkeypatch):
    monkeypatch.setattr(settings, "TINY_TOKEN", "")
    r = client_comercial.post("/empresas", json=_payload())
    assert r.json()["tiny_status"] is None and agendados == []


def test_reenviar_pela_rota(client_comercial, agendados, db_session):
    eid = client_comercial.post("/empresas", json=_payload()).json()["id"]
    agendados.clear()
    emp = db_session.get(Empresa, eid)
    emp.tiny_status, emp.tiny_erro = "erro", "Cidade não encontrada"
    db_session.commit()

    r = client_comercial.post(f"/empresas/{eid}/tiny")
    assert r.status_code == 200
    assert r.json()["tiny_status"] == "pendente" and r.json()["tiny_erro"] is None
    assert agendados == [eid]


def test_reenviar_exige_funcao(client_lab, db_session):
    emp = Empresa(nome="Filial", cgc=CNPJ_A)
    db_session.add(emp); db_session.commit()
    assert client_lab.post(f"/empresas/{emp.id}/tiny").status_code == 403


def test_reenviar_empresa_inexistente_404(client_comercial):
    assert client_comercial.post("/empresas/9999/tiny").status_code == 404


def test_listar_filtra_por_tiny_status(client_comercial, db_session):
    db_session.add_all([
        Empresa(nome="Com erro", cgc=CNPJ_A, tiny_status="erro", tiny_erro="Cidade"),
        Empresa(nome="Enviada", cgc=CNPJ_B, tiny_status="enviada", tiny_id=999),
    ])
    db_session.commit()
    assert client_comercial.get("/empresas?tiny_status=erro").json()["total"] == 1
    assert client_comercial.get("/empresas?tiny_status=enviada").json()["items"][0]["tiny_id"] == 999
    assert client_comercial.get("/empresas").json()["total"] == 2


def test_empresa_nova_pela_proposta_agenda_depois_do_commit(client_comercial, agendados, db_session):
    cli = Cliente(nome="ACME", cgc="08857492000148")
    db_session.add(cli); db_session.commit()
    r = client_comercial.post("/propostas", json={
        "destinatario": {"tipo": "nova_empresa", "documento": CNPJ_A, "matriz": cli.id,
                         "nome": "Filial da Proposta", "email": "f@acme.com", "telefone": "8130001111"},
    })
    assert r.status_code == 201
    empresa_id = r.json()["empresa"]
    assert agendados == [empresa_id]
    assert db_session.get(Empresa, empresa_id).tiny_status == "pendente"


def _cliente(db_session):
    cli = Cliente(nome="ACME", cgc="08857492000148")
    db_session.add(cli); db_session.commit()
    return cli


def test_empresa_editada_pela_proposta_agenda_o_envio(client_comercial, agendados, db_session):
    """A spec manda sincronizar quando a Empresa e' criada E quando e' editada —
    e o modal da proposta edita o cadastro inteiro da empresa escolhida."""
    cli = _cliente(db_session)
    emp = Empresa(nome="Filial Existente", cgc=CNPJ_A, cliente=cli.id)
    db_session.add(emp); db_session.commit()
    agendados.clear()
    r = client_comercial.post("/propostas", json={
        "destinatario": {"tipo": "empresa", "id": emp.id, "nome": "Filial Renomeada",
                         "email": "f@acme.com", "telefone": "8130001111"},
    })
    assert r.status_code == 201
    assert agendados == [emp.id]
    db_session.refresh(emp)
    assert emp.nome == "Filial Renomeada" and emp.tiny_status == "pendente"


def test_empresa_editada_pela_proposta_agenda_no_put(client_comercial, agendados, db_session):
    cli = _cliente(db_session)
    emp = Empresa(nome="Filial Existente", cgc=CNPJ_A, cliente=cli.id)
    db_session.add(emp); db_session.commit()
    pid = client_comercial.post("/propostas", json={
        "destinatario": {"tipo": "empresa", "id": emp.id, "nome": "Filial",
                         "email": "f@acme.com", "telefone": "8130001111"},
    }).json()["id"]
    agendados.clear()
    r = client_comercial.put(f"/propostas/{pid}", json={
        "destinatario": {"tipo": "empresa", "id": emp.id, "nome": "Filial Corrigida",
                         "email": "f@acme.com", "telefone": "8130001111"},
    })
    assert r.status_code == 200 and agendados == [emp.id]


def test_falha_ao_marcar_pendente_nao_derruba_a_rota(db_session):
    """A proposta ja foi salva quando o agendamento roda: um erro no `db.get` ou
    no commit devolvia 500 para uma proposta que existe de verdade."""
    from types import SimpleNamespace
    from app.api.propostas import _agendar_empresa_no_tiny

    class BancoQuebrado:
        def get(self, *a, **k):
            raise RuntimeError("banco fora do ar")

    tarefas = SimpleNamespace(add_task=lambda *a, **k: None)
    _agendar_empresa_no_tiny(BancoQuebrado(), tarefas,
                             SimpleNamespace(empresa_para_tiny=1))   # nao levanta


def test_falha_do_tiny_nao_derruba_a_proposta(client_comercial, monkeypatch, db_session):
    def explode(*a, **k):
        raise RuntimeError("Tiny fora do ar")

    import app.api.propostas as api_propostas
    monkeypatch.setattr(api_propostas.tiny_client, "sincronizar_empresa", explode)
    cli = Cliente(nome="ACME", cgc="08857492000148")
    db_session.add(cli); db_session.commit()
    r = client_comercial.post("/propostas", json={
        "destinatario": {"tipo": "nova_empresa", "documento": CNPJ_B, "matriz": cli.id,
                         "nome": "Filial", "email": "f@acme.com", "telefone": "8130001111"},
    })
    assert r.status_code == 201  # a proposta foi salva mesmo assim
