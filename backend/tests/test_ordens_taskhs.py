import pytest

from app.core.config import settings
from app.integrations import taskhs_client


def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


@pytest.fixture()
def captura(monkeypatch):
    """Liga a integração e captura os payloads agendados (sem HTTP real)."""
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "http://taskhs.test/api")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "k-123")
    chamadas = []
    monkeypatch.setattr(taskhs_client, "enviar_card", lambda payload: chamadas.append(payload))
    return chamadas


def test_abrir_agenda_card_recebido(client, usuario_comum, fases_seed, os_base, caixa_base, captura):
    h = _headers(client, "comum", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
        "caixa": caixa_base,
    }, headers=h)
    assert r.status_code == 201
    assert len(captura) == 1
    p = captura[0]
    assert p["external_id"] == str(r.json()["id"])
    assert p["list"] == "🚚 Expedição (Abrindo caixa)"
    assert p["archived"] is False


def test_abrir_sem_integracao_nao_agenda(client, usuario_comum, fases_seed, os_base, caixa_base, monkeypatch):
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "")
    chamadas = []
    monkeypatch.setattr(taskhs_client, "enviar_card", lambda payload: chamadas.append(payload))
    h = _headers(client, "comum", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
        "caixa": caixa_base,
    }, headers=h)
    assert r.status_code == 201
    assert chamadas == []


def test_avancar_agenda_card_laboratorio(client, usuario_comum, fases_seed, os_base, caixa_base, captura):
    # avançar de Recebido(4)→Laboratório(5) exige a função da fase de origem = Expedição (usuario_comum)
    h = _headers(client, "comum", "senha123")
    oid = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
        "caixa": caixa_base,
    }, headers=h).json()["id"]
    captura.clear()  # ignora o card da abertura
    r = client.post(f"/ordens/{oid}/avancar", json={}, headers=h)
    assert r.status_code == 200
    assert len(captura) == 1
    assert captura[0]["list"] == "🔬Laboratório Calibração"
    assert captura[0]["archived"] is False


def test_cancelar_agenda_card_arquivado_na_lista_de_origem(client, usuario_comum, fases_seed, os_base, caixa_base, captura):
    h = _headers(client, "comum", "senha123")
    oid = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
        "caixa": caixa_base,
    }, headers=h).json()["id"]
    captura.clear()
    r = client.post(f"/ordens/{oid}/cancelar", json={"motivo": "desistencia"}, headers=h)
    assert r.status_code == 200
    assert len(captura) == 1
    p = captura[0]
    assert p["archived"] is True
    assert p["list"] == "🚚 Expedição (Abrindo caixa)"  # fase de origem (Recebido)


def test_abrir_descricao_no_payload(client, usuario_comum, fases_seed, os_base, caixa_base, captura):
    h = _headers(client, "comum", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
        "caixa": caixa_base,
    }, headers=h)
    assert r.status_code == 201
    p = captura[0]
    assert "Cliente: Cliente OS" in p["description"]
    assert "📋 Recebido" in p["description"]
    assert "🤝 Pós-Vendas" not in p["description"]  # ainda em Recebido


def test_descricao_inclui_link_certificado(client, usuario_comum, fases_seed,
                                           os_base, caixa_base, captura, db_session, monkeypatch):
    from app.core.config import settings
    from app.models import OSCertificado
    monkeypatch.setattr(settings, "CERT_PUBLIC_BASE_URL", "http://localhost:8001")
    h = _headers(client, "comum", "senha123")
    oid = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
        "caixa": caixa_base,
    }, headers=h).json()["id"]
    # simula laboratorio concluido: certificado ja gravado para a OS
    db_session.add(OSCertificado(os=oid, tipo="C", html="<html/>"))
    db_session.commit()
    captura.clear()
    # avanca Recebido(4)->Laboratorio(5) — funcao da fase de origem = Expedicao (usuario_comum)
    r = client.post(f"/ordens/{oid}/avancar", json={}, headers=h)
    assert r.status_code == 200
    assert f"Certificado de Calibração: http://localhost:8001/publico/certificado/{oid}/calibracao?t=" \
        in captura[-1]["description"]
