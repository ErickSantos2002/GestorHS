import pytest

from app.core.config import settings
from app.integrations import taskhs_client


def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
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
    h = _headers(client, "comum@hs.com", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
        "caixa": caixa_base,
    }, headers=h)
    assert r.status_code == 201
    assert len(captura) == 1
    p = captura[0]
    assert p["external_id"] == str(r.json()["id"])
    assert p["list_id"] == 196
    assert p["archived"] is False


def test_abrir_sem_integracao_nao_agenda(client, usuario_comum, fases_seed, os_base, caixa_base, monkeypatch):
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "")
    chamadas = []
    monkeypatch.setattr(taskhs_client, "enviar_card", lambda payload: chamadas.append(payload))
    h = _headers(client, "comum@hs.com", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
        "caixa": caixa_base,
    }, headers=h)
    assert r.status_code == 201
    assert chamadas == []


def test_abrir_obs_no_payload(client, usuario_comum, fases_seed, os_base, caixa_base, captura):
    h = _headers(client, "comum@hs.com", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
        "caixa": caixa_base,
    }, headers=h)
    assert r.status_code == 201
    p = captura[0]
    assert "Cliente: Cliente OS" in p["obs1"]  # cabeçalho no topo da obs1
    assert p["obs3"] is None  # ainda em Recebido, sem Pós-Vendas
    assert "description" not in p


def test_upload_nota_fiscal_reagenda_card(client, usuario_financeiro, fases_seed,
                                          os_base, db_session, upload_tmp, captura):
    import io
    from app.models import Ordem
    # OS ja em Financeiro (fase 10) — upload da NF deve reespelhar o card sem precisar avancar a OS
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"],
              fase=10, tipo_servico="C", situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    h = _headers(client, "fin@hs.com", "senha123")
    captura.clear()
    r = client.post(f"/ordens/{o.id}/nota-fiscal",
                     files={"arquivo_pdf": ("nf.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf"),
                            "arquivo_xml": ("nf.xml", io.BytesIO(b"<nfse/>"), "application/xml")},
                     data={"numero": "555"}, headers=h)
    assert r.status_code == 200
    assert len(captura) == 1
    assert captura[0]["list_id"] == 205
    assert "Nota fiscal:" in captura[0]["obs4"]
