"""Caixa com modulo/phoebus nao vira card no TaskHS — nem ao avancar, nem ao cancelar."""
import pytest

from app.core.config import settings
from app.integrations import taskhs_client


@pytest.fixture()
def captura(monkeypatch):
    """Liga a integracao e captura os payloads agendados (sem HTTP real)."""
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "http://taskhs.test/api")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "k-123")
    chamadas = []
    monkeypatch.setattr(taskhs_client, "enviar_card", lambda payload: chamadas.append(payload))
    return chamadas


def _caixa_com(db, *, catalogo_id, fase=4, desfecho="pendente", fase_os=None):
    """Caixa na fase informada com 1 OS de um equipamento do catalogo `catalogo_id`.

    O id do catalogo e' explicito (nao autoincrement) porque a regra depende dele.
    """
    from app.models import Caixa, Cliente, Equipamento, EquipamentoCliente, Ordem
    cli = Cliente(nome="Cliente Bloqueio")
    eq = Equipamento(id=catalogo_id, descricao=f"Equipamento {catalogo_id}")
    db.add_all([cli, eq]); db.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie=f"SER-{catalogo_id}")
    cx = Caixa(obs="Caixa bloqueio", fase=fase)
    db.add_all([ec, cx]); db.flush()
    o = Ordem(cliente=cli.id, equipamento_cliente=ec.id,
              fase=fase_os if fase_os is not None else fase,
              situacao="E", caixa=cx.id, desfecho_lab=desfecho)
    db.add(o); db.commit(); db.refresh(cx)
    return cx.id, o.id


def test_avancar_caixa_de_modulo_nao_espelha(client_exp, db_session, captura):
    cx_id, _ = _caixa_com(db_session, catalogo_id=settings.EQUIPAMENTO_MODULO_ID)
    r = client_exp.post(f"/caixas/{cx_id}/avancar", json={})
    assert r.status_code == 200
    assert captura == []


def test_avancar_caixa_de_phoebus_nao_espelha(client_exp, db_session, captura):
    cx_id, _ = _caixa_com(db_session, catalogo_id=settings.EQUIPAMENTO_PHOEBUS_ID)
    r = client_exp.post(f"/caixas/{cx_id}/avancar", json={})
    assert r.status_code == 200
    assert captura == []


def test_avancar_caixa_comum_continua_espelhando(client_exp, db_session, captura):
    """Controle positivo: sem o gate mordendo quem nao e' modulo, o teste acima
    passaria mesmo com a integracao quebrada."""
    cx_id, _ = _caixa_com(db_session, catalogo_id=1)
    r = client_exp.post(f"/caixas/{cx_id}/avancar", json={})
    assert r.status_code == 200
    assert len(captura) == 1
    assert captura[0]["external_id"] == str(cx_id)


def test_avancar_caixa_mista_nao_espelha(client_exp, db_session, captura):
    """Caixa mista: uma OS de modulo contamina a caixa inteira."""
    from app.models import Cliente, Equipamento, EquipamentoCliente, Ordem
    cx_id, _ = _caixa_com(db_session, catalogo_id=1)
    cli = db_session.query(Cliente).first()
    eq_mod = Equipamento(id=settings.EQUIPAMENTO_MODULO_ID, descricao="Modulo")
    db_session.add(eq_mod); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq_mod.id, serie="SER-MOD")
    db_session.add(ec); db_session.flush()
    db_session.add(Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=4,
                         situacao="E", caixa=cx_id))
    db_session.commit()
    r = client_exp.post(f"/caixas/{cx_id}/avancar", json={})
    assert r.status_code == 200
    assert captura == []


def test_caixa_cujo_modulo_esta_cancelado_volta_a_espelhar(client_exp, db_session, captura):
    """OS de modulo CANCELADA (fase 9) nao conta — a caixa volta a gerar card."""
    from app.models import Cliente, Equipamento, EquipamentoCliente, Ordem
    cx_id, _ = _caixa_com(db_session, catalogo_id=1)
    cli = db_session.query(Cliente).first()
    eq_mod = Equipamento(id=settings.EQUIPAMENTO_MODULO_ID, descricao="Modulo")
    db_session.add(eq_mod); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq_mod.id, serie="SER-MOD")
    db_session.add(ec); db_session.flush()
    db_session.add(Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=9,
                         situacao="C", caixa=cx_id))
    db_session.commit()
    r = client_exp.post(f"/caixas/{cx_id}/avancar", json={})
    assert r.status_code == 200
    assert len(captura) == 1


def test_cancelar_caixa_de_modulo_nao_arquiva_card(client_exp, db_session, captura):
    cx_id, _ = _caixa_com(db_session, catalogo_id=settings.EQUIPAMENTO_MODULO_ID)
    r = client_exp.post(f"/caixas/{cx_id}/cancelar", json={"motivo": "teste"})
    assert r.status_code == 200
    assert captura == []


def test_bloqueio_registra_log_pulado(client_exp, db_session, captura, monkeypatch):
    from app.api import espelhamento
    logs = []
    monkeypatch.setattr(espelhamento, "registrar_log_integracao",
                        lambda **kw: logs.append(kw))
    cx_id, _ = _caixa_com(db_session, catalogo_id=settings.EQUIPAMENTO_MODULO_ID)
    client_exp.post(f"/caixas/{cx_id}/avancar", json={})
    assert logs and logs[0]["status"] == "pulado"
    assert logs[0]["motivo"] == "caixa_de_modulo"
    assert logs[0]["integracao"] == "taskhs"
