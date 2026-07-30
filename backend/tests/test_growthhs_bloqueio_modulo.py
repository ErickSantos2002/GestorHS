"""Caixa com modulo/phoebus nao vira card de caixa no GrowthHS.

Fora do escopo (e NAO testado aqui como bloqueio): as cargas por CLIENTE
(atrasados/vencendo) continuam mandando modulo — ver a spec.
"""
from types import SimpleNamespace

import pytest

from app.api import growthhs_cards
from app.core.config import settings


class _BG:
    def __init__(self):
        self.tarefas = []

    def add_task(self, fn, *a, **k):
        self.tarefas.append((fn, a, k))


@pytest.fixture()
def growth_ligado(monkeypatch):
    monkeypatch.setattr(settings, "HSGROWTH_BASE_URL", "https://growth.test")
    monkeypatch.setattr(settings, "HSGROWTH_API_KEY", "k")


def _caixa_com(db, catalogo_id):
    from app.models import Caixa, Cliente, Equipamento, EquipamentoCliente, Ordem
    cli = Cliente(nome="Cliente Growth", cgc="11222333000144")
    eq = Equipamento(id=catalogo_id, descricao=f"Eq {catalogo_id}")
    db.add_all([cli, eq]); db.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie=f"S{catalogo_id}")
    cx = Caixa(obs="Caixa growth", fase=6)
    db.add_all([ec, cx]); db.flush()
    o = Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=6, situacao="E",
              caixa=cx.id, desfecho_lab="liberado")
    db.add(o); db.commit(); db.refresh(cx)
    return cx


def test_card_caixa_de_modulo_nao_agenda(db_session, fases_seed, growth_ligado):
    cx = _caixa_com(db_session, settings.EQUIPAMENTO_MODULO_ID)
    bg = _BG()
    growthhs_cards.agendar_card_caixa(db_session, bg, cx)
    assert bg.tarefas == []


def test_card_caixa_de_phoebus_nao_agenda(db_session, fases_seed, growth_ligado):
    cx = _caixa_com(db_session, settings.EQUIPAMENTO_PHOEBUS_ID)
    bg = _BG()
    growthhs_cards.agendar_card_caixa(db_session, bg, cx)
    assert bg.tarefas == []


def test_card_caixa_comum_continua_agendando(db_session, fases_seed, growth_ligado):
    """Controle positivo."""
    cx = _caixa_com(db_session, 1)
    bg = _BG()
    growthhs_cards.agendar_card_caixa(db_session, bg, cx)
    assert len(bg.tarefas) == 1


def test_bloqueio_de_caixa_registra_log(db_session, fases_seed, growth_ligado, monkeypatch):
    logs = []
    monkeypatch.setattr(growthhs_cards, "registrar_log_integracao",
                        lambda **kw: logs.append(kw))
    cx = _caixa_com(db_session, settings.EQUIPAMENTO_MODULO_ID)
    growthhs_cards.agendar_card_caixa(db_session, _BG(), cx)
    assert logs and logs[0]["status"] == "pulado"
    assert logs[0]["motivo"] == "caixa_de_modulo"
    assert logs[0]["integracao"] == "growthhs"


def _caixa_com_ordens(db, especificacoes):
    """especificacoes: lista de (catalogo_id, fase, desfecho_lab, serie). Cria uma
    OS por especificacao, todas na mesma caixa; um catalogo so' vira uma linha
    de Equipamento mesmo se repetido."""
    from app.models import Caixa, Cliente, Equipamento, EquipamentoCliente, Ordem
    cli = Cliente(nome="Cliente Growth", cgc="11222333000144")
    db.add(cli); db.flush()
    cx = Caixa(obs="Caixa growth", fase=6)
    db.add(cx); db.flush()
    catalogos_criados: dict[int, None] = {}
    for catalogo, fase, desfecho, serie in especificacoes:
        if catalogo not in catalogos_criados:
            db.add(Equipamento(id=catalogo, descricao=f"Eq {catalogo}"))
            db.flush()
            catalogos_criados[catalogo] = None
        ec = EquipamentoCliente(cliente=cli.id, equipamento=catalogo, serie=serie)
        db.add(ec); db.flush()
        db.add(Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=fase, situacao="E",
                     caixa=cx.id, desfecho_lab=desfecho))
    db.commit(); db.refresh(cx)
    return cx


def test_device_de_os_modulo_cancelada_nao_vaza_no_card(db_session, fases_seed, growth_ligado):
    """O gate deixa passar (OS de modulo cancelada nao conta pro bloqueio), mas o
    modulo NAO pode aparecer na lista de devices do card enviado."""
    cx = _caixa_com_ordens(db_session, [
        (1, 6, "liberado", "S-ATIVA"),
        (settings.EQUIPAMENTO_MODULO_ID, 9, "pendente", "S-MODULO"),
    ])
    bg = _BG()
    growthhs_cards.agendar_card_caixa(db_session, bg, cx)
    assert len(bg.tarefas) == 1
    card = bg.tarefas[0][1][0]
    seriais = [d["serial_number"] for d in card["devices"]]
    assert seriais == ["S-ATIVA"]


def test_device_de_os_comum_cancelada_nao_aparece_no_card(db_session, fases_seed, growth_ligado):
    cx = _caixa_com_ordens(db_session, [
        (1, 6, "liberado", "S-ATIVA"),
        (2, 9, "pendente", "S-CANCELADA"),
    ])
    bg = _BG()
    growthhs_cards.agendar_card_caixa(db_session, bg, cx)
    assert len(bg.tarefas) == 1
    card = bg.tarefas[0][1][0]
    seriais = [d["serial_number"] for d in card["devices"]]
    assert seriais == ["S-ATIVA"]


def test_card_os_de_modulo_nao_agenda(growth_ligado, monkeypatch):
    """`agendar_card_os` nao tem call site em producao hoje, mas e' gateado para
    nao voltar furado."""
    logs = []
    monkeypatch.setattr(growthhs_cards, "registrar_log_integracao",
                        lambda **kw: logs.append(kw))
    ordem = SimpleNamespace(
        id=77,
        equipamento_rel=SimpleNamespace(equipamento=settings.EQUIPAMENTO_MODULO_ID),
        equipamento_catalogo=settings.EQUIPAMENTO_MODULO_ID,
    )
    bg = _BG()
    growthhs_cards.agendar_card_os(db=None, background_tasks=bg, ordem=ordem)
    assert bg.tarefas == []
    assert logs and logs[0]["motivo"] == "caixa_de_modulo"
