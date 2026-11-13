"""`PUT /caixas/{id}/proposta` — corrige o numero da proposta da caixa pela tela.

O numero vem digitado a mao no card do GrowthHS; antes desta rota, erro de
digitacao so se corrigia com `corrigir_proposta_caixa` + sync manual do TaskHS.
A trava e' a mesma do script (proposta do MESMO cliente da caixa) e a troca
reespelha o card da caixa, que mostra "Proposta #N" na obs3.
"""
import pytest

from app.core.config import settings
from app.integrations import taskhs_client


def _logar(client, email):
    tok = client.post("/auth/login", json={"email": email, "senha": "senha123"}).json()
    client.headers["Authorization"] = f"Bearer {tok['access_token']}"


@pytest.fixture()
def captura(monkeypatch):
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "http://taskhs.test/api")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "k-123")
    chamadas = []
    monkeypatch.setattr(taskhs_client, "enviar_card", lambda payload: chamadas.append(payload))
    return chamadas


@pytest.fixture()
def cenario(db_session, fases_seed):
    """Caixa no Financeiro apontando para a proposta 474 (PM-SP) quando devia ser a
    476 (Phoenix) — o caso da caixa 1212. Mais uma proposta de outro cliente."""
    from app.models import Caixa, Cliente, Ordem, Proposta
    pm = Cliente(nome="POLICIA MILITAR")
    phoenix = Cliente(nome="PHOENIX DO PECEM")
    outro = Cliente(nome="OUTRO CLIENTE")
    db_session.add_all([pm, phoenix, outro])
    db_session.flush()
    cx = Caixa(fase=10, cliente_principal=phoenix.id, numero_proposta=474)
    db_session.add(cx)
    db_session.flush()
    os_ = Ordem(cliente=phoenix.id, situacao="E", fase=10, caixa=cx.id, tipo_servico="C")
    db_session.add(os_)
    db_session.add_all([
        Proposta(numero=474, cliente=pm.id),
        Proposta(numero=476, cliente=phoenix.id),
        Proposta(numero=480, cliente=outro.id),
        Proposta(numero=481, cliente=phoenix.id, is_deleted=True),
    ])
    db_session.commit()
    db_session.refresh(cx)
    return {"caixa": cx, "ordem": os_}


def test_comercial_troca_a_proposta_e_registra_no_log(client, usuario_comercial, cenario, db_session):
    from app.models import LogOS
    _logar(client, "comercial@hs.com")
    cx = cenario["caixa"]
    r = client.put(f"/caixas/{cx.id}/proposta", json={"numero": 476})
    assert r.status_code == 200, r.text
    assert r.json()["numero_proposta"] == 476
    db_session.refresh(cx)
    assert cx.numero_proposta == 476
    textos = [l.texto for l in db_session.query(LogOS).filter(LogOS.os == cenario["ordem"].id)]
    assert f"Caixa #{cx.id}: proposta #474 -> #476" in textos


def test_admin_tambem_troca(client, usuario_admin, cenario):
    _logar(client, "admin@hs.com")
    r = client.put(f"/caixas/{cenario['caixa'].id}/proposta", json={"numero": 476})
    assert r.status_code == 200


@pytest.mark.parametrize("usuario,email", [
    ("usuario_financeiro", "fin@hs.com"),
    ("usuario_comum", "comum@hs.com"),
    ("usuario_lab", "lab@hs.com"),
])
def test_outras_funcoes_levam_403(request, client, cenario, usuario, email):
    request.getfixturevalue(usuario)
    _logar(client, email)
    r = client.put(f"/caixas/{cenario['caixa'].id}/proposta", json={"numero": 476})
    assert r.status_code == 403


def test_reespelha_o_card_da_caixa_com_o_numero_novo(client, usuario_comercial, cenario, captura):
    _logar(client, "comercial@hs.com")
    cx = cenario["caixa"]
    captura.clear()
    r = client.put(f"/caixas/{cx.id}/proposta", json={"numero": 476})
    assert r.status_code == 200
    assert len(captura) == 1
    assert captura[0]["external_id"] == str(cx.id)
    assert captura[0]["list_id"] == 205          # lista da fase atual (Financeiro)
    assert "Proposta #476" in captura[0]["obs3"]


def test_numero_igual_nao_grava_nem_reespelha(client, usuario_comercial, cenario, captura, db_session):
    from app.models import LogOS
    _logar(client, "comercial@hs.com")
    cx = cenario["caixa"]
    captura.clear()
    r = client.put(f"/caixas/{cx.id}/proposta", json={"numero": 474})
    assert r.status_code == 200
    assert captura == []
    assert db_session.query(LogOS).filter(LogOS.os == cenario["ordem"].id).count() == 0


def test_proposta_de_outro_cliente_e_recusada(client, usuario_comercial, cenario, db_session):
    _logar(client, "comercial@hs.com")
    cx = cenario["caixa"]
    r = client.put(f"/caixas/{cx.id}/proposta", json={"numero": 480})
    assert r.status_code == 422
    db_session.refresh(cx)
    assert cx.numero_proposta == 474


def test_proposta_desabilitada_e_recusada(client, usuario_comercial, cenario):
    _logar(client, "comercial@hs.com")
    r = client.put(f"/caixas/{cenario['caixa'].id}/proposta", json={"numero": 481})
    assert r.status_code == 422


def test_proposta_inexistente_404(client, usuario_comercial, cenario):
    _logar(client, "comercial@hs.com")
    r = client.put(f"/caixas/{cenario['caixa'].id}/proposta", json={"numero": 99999})
    assert r.status_code == 404


def test_caixa_inexistente_404(client, usuario_comercial, cenario):
    _logar(client, "comercial@hs.com")
    assert client.put("/caixas/98765/proposta", json={"numero": 476}).status_code == 404


@pytest.mark.parametrize("fase", [4, 5, 6, 10, 7])
def test_fases_permitidas(client, usuario_comercial, cenario, db_session, fase):
    cx = cenario["caixa"]
    cx.fase = fase
    cenario["ordem"].fase = fase
    db_session.commit()
    _logar(client, "comercial@hs.com")
    assert client.put(f"/caixas/{cx.id}/proposta", json={"numero": 476}).status_code == 200


@pytest.mark.parametrize("fase", [8, 9, None])
def test_fora_da_janela_409(client, usuario_comercial, cenario, db_session, fase):
    """Depois da 7 o card pode estar numa lista que o GestorHS nao conhece
    (209/210) e reespelhar o arrastaria de volta."""
    cx = cenario["caixa"]
    cx.fase = fase
    db_session.commit()
    _logar(client, "comercial@hs.com")
    r = client.put(f"/caixas/{cx.id}/proposta", json={"numero": 476})
    assert r.status_code == 409
    db_session.refresh(cx)
    assert cx.numero_proposta == 474
