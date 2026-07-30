import pytest

from app.core.config import settings
from app.scripts import sincronizar_taskhs


def _abrir_os(db, os_base, fase):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"],
              fase=fase, tipo_servico="C", situacao="E")
    db.add(o); db.commit(); db.refresh(o)
    return o


def test_sincronizar_envia_so_fases_4_a_8(db_session, os_base, fases_seed, monkeypatch):
    from app.api import espelhamento
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "http://t/api")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "k")
    _abrir_os(db_session, os_base, 4)
    _abrir_os(db_session, os_base, 8)
    _abrir_os(db_session, os_base, 9)  # cancelada: ignorada
    _abrir_os(db_session, os_base, 10)
    enviados = []
    monkeypatch.setattr(espelhamento, "espelhar_os_sync",
                        lambda db, ordem, *, list_id, arquivado=False: (
                            enviados.append((ordem.fase, list_id)) or True))
    enviadas, total = sincronizar_taskhs.sincronizar(db_session)
    assert enviadas == 3
    assert total == 3
    assert sorted(f for f, _ in enviados) == [4, 8, 10]
    assert {lid for _, lid in enviados} == {196, 210, 205}


def test_sincronizar_desligada_levanta(db_session, monkeypatch):
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "")
    with pytest.raises(RuntimeError):
        sincronizar_taskhs.sincronizar(db_session)


def test_sincronizar_nao_conta_os_de_modulo_como_enviada(db_session, fases_seed, monkeypatch):
    """OS de modulo e' pulada; o relatorio nao pode contar como enviada."""
    from app.models import Cliente, Equipamento, EquipamentoCliente, Ordem
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "http://t/api")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "k")
    cli = Cliente(nome="C")
    eq_mod = Equipamento(id=settings.EQUIPAMENTO_MODULO_ID, descricao="Modulo")
    eq_com = Equipamento(id=1, descricao="Bafometro")
    db_session.add_all([cli, eq_mod, eq_com]); db_session.flush()
    ec_mod = EquipamentoCliente(cliente=cli.id, equipamento=eq_mod.id, serie="M1")
    ec_com = EquipamentoCliente(cliente=cli.id, equipamento=eq_com.id, serie="B1")
    db_session.add_all([ec_mod, ec_com]); db_session.flush()
    db_session.add_all([
        Ordem(cliente=cli.id, equipamento_cliente=ec_mod.id, fase=4, situacao="E"),
        Ordem(cliente=cli.id, equipamento_cliente=ec_com.id, fase=4, situacao="E"),
    ])
    db_session.commit()
    enviados = []
    monkeypatch.setattr("app.integrations.taskhs_client.enviar_card_sync",
                        lambda p: enviados.append(p))
    enviadas, total = sincronizar_taskhs.sincronizar(db_session)
    assert total == 2
    assert enviadas == 1
    assert len(enviados) == 1
