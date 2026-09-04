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
    """O card e' da CAIXA: `external_id` e' o id dela, nunca o da OS."""
    h = _headers(client, "comum@hs.com", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
        "caixa": caixa_base,
    }, headers=h)
    assert r.status_code == 201
    assert len(captura) == 1
    p = captura[0]
    assert p["external_id"] == str(caixa_base)
    assert p["title"].startswith(f"CX {caixa_base} ·")
    assert "OS #" not in p["title"]
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


def test_anexar_nota_fiscal_reagenda_card(client, usuario_financeiro, fases_seed,
                                          os_base, caixa_base, db_session, upload_tmp, captura):
    """Anexar a nota reespelha o card da CAIXA sem precisar avancar nada — e um
    card so, nunca um por OS.

    O `POST /ordens/{id}/nota-fiscal` que este teste usava sumiu; o caminho de
    anexo agora e' o da caixa. A linha do NUMERO no `obs4` deixou de vir da
    coluna legada e passa pela tabela `notas_fiscais`; a FORMATACAO dessa linha
    tem cobertura de unidade em `test_taskhs_caixa.py` (chamada direta a
    `montar_obs_caixa`) — o que se afirma AQUI e' outra coisa: que a nota anexada
    chega mesmo ao card.
    """
    import io
    from app.models import Caixa, Ordem
    cx = db_session.get(Caixa, caixa_base)
    cx.fase = 10
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"],
              fase=10, tipo_servico="C", situacao="E", caixa=cx.id)
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    h = _headers(client, "fin@hs.com", "senha123")
    captura.clear()
    r = client.post(f"/caixas/{caixa_base}/notas-fiscais",
                    files=[("arquivos_pdf", ("nf.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")),
                           ("arquivos_xml", ("nf.xml", io.BytesIO(b"<nfse/>"), "application/xml"))],
                    data={"numeros": ["555"]}, headers=h)
    assert r.status_code == 200
    assert len(captura) == 1
    assert captura[0]["external_id"] == str(caixa_base)
    assert captura[0]["list_id"] == 205
    # Cobertura de INTEGRACAO, nao de unidade: e' o unico teste que percorre
    # HTTP -> agendar_espelhamento_caixa -> _montar_payload_caixa -> obs4. Os
    # testes de `test_taskhs_caixa.py` chamam montar_obs_caixa direto e nao
    # pegariam um `notas=notas` esquecido na chamada de espelhamento.py.
    assert "NF 555" in captura[0]["obs4"]
