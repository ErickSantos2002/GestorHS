from datetime import date


def _equip(db_session, os_base, serie, equipamento=None):
    from app.models import Equipamento, EquipamentoCliente
    equipamento_id = equipamento or os_base["equipamento"]
    # FK: `equipamentos_cliente.equipamento` referencia o catalogo `equipamentos`.
    # `os_base` ja cria a linha padrao; ids customizados (ex.: EQUIPAMENTO_MODULO_ID)
    # precisam da propria linha de catalogo antes de serem usados aqui.
    if equipamento is not None and db_session.get(Equipamento, equipamento_id) is None:
        db_session.add(Equipamento(id=equipamento_id, descricao="Modulo de Calibracao"))
        db_session.commit()
    ec = EquipamentoCliente(cliente=os_base["cliente"],
                            equipamento=equipamento_id, serie=serie)
    db_session.add(ec); db_session.commit(); db_session.refresh(ec)
    return ec


def _instalar(db_session, modulo_id, phoebus_id):
    from app.models import InstalacaoModulo
    i = InstalacaoModulo(modulo=modulo_id, phoebus=phoebus_id,
                         entrou_em=date(2026, 7, 18), origem="teste")
    db_session.add(i); db_session.commit()
    return i


def test_fase_laboratorio_tem_constante():
    from app.core import os_workflow as wf
    assert wf.FASE_LABORATORIO == 5
    assert wf.PROXIMA[wf.FASE_LABORATORIO] == 6      # laboratorio -> pos-vendas


def test_elo_none_quando_nao_e_modulo(db_session, os_base):
    from app.api.growthhs_cards import buscar_elo
    ec = _equip(db_session, os_base, "SN-1")          # equipamento comum
    assert buscar_elo(db_session, ec) is None


def test_elo_none_quando_modulo_sem_instalacao(db_session, os_base):
    from app.api.growthhs_cards import buscar_elo
    from app.core.config import settings
    mod = _equip(db_session, os_base, "F001", equipamento=settings.EQUIPAMENTO_MODULO_ID)
    assert buscar_elo(db_session, mod) is None


def test_elo_traz_o_phoebus_com_a_ponte_de_atributos(db_session, os_base):
    """A ponte e obrigatoria: montar_device espera .descricao, o ORM expoe
    .equipamento_descricao. Sem ela, quebra com AttributeError."""
    from app.api.growthhs_cards import buscar_elo
    from app.core.config import settings
    pho = _equip(db_session, os_base, "WATFR01-00340")
    mod = _equip(db_session, os_base, "F005065", equipamento=settings.EQUIPAMENTO_MODULO_ID)
    _instalar(db_session, mod.id, pho.id)

    elo = buscar_elo(db_session, mod)
    assert elo is not None
    assert elo.serie == "WATFR01-00340"
    assert hasattr(elo, "descricao")          # o nome que montar_device consome
    # e o elo funciona de ponta a ponta no montar_device:
    from app.core.growthhs_payload import montar_device
    d = montar_device(mod, "Modulo de Calibracao", elo=elo)
    assert d["serial_number"] == "WATFR01-00340"
    assert d["alcohol_module"] == "F005065"
