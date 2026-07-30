"""O reenvio manual tambem respeita o bloqueio de modulo/phoebus."""
from app.core.config import settings
from app.scripts import reenviar_os_taskhs


def _os_com(db, catalogo_id, fase=4):
    from app.models import Cliente, Equipamento, EquipamentoCliente, Ordem
    cli = Cliente(nome="C")
    eq = Equipamento(id=catalogo_id, descricao=f"Eq {catalogo_id}")
    db.add_all([cli, eq]); db.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie=f"S{catalogo_id}")
    db.add(ec); db.flush()
    o = Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=fase, situacao="E")
    db.add(o); db.commit(); db.refresh(o)
    return o.id


def test_reenviar_pula_os_de_modulo(db_session, fases_seed, monkeypatch, capsys):
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "http://t/api")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "k")
    enviados = []
    monkeypatch.setattr("app.integrations.taskhs_client.enviar_card_sync",
                        lambda p: enviados.append(p))
    os_id = _os_com(db_session, settings.EQUIPAMENTO_MODULO_ID)
    ok, total = reenviar_os_taskhs.reenviar(db_session, [os_id], enviar=True)
    assert enviados == []
    assert ok == 0
    assert "PULA" in capsys.readouterr().out


def test_reenviar_envia_os_comum(db_session, fases_seed, monkeypatch):
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "http://t/api")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "k")
    enviados = []
    monkeypatch.setattr("app.integrations.taskhs_client.enviar_card_sync",
                        lambda p: enviados.append(p))
    os_id = _os_com(db_session, 1)
    ok, total = reenviar_os_taskhs.reenviar(db_session, [os_id], enviar=True)
    assert len(enviados) == 1
    assert ok == 1
