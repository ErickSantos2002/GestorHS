"""Backfill das caixas de Phoebus/Modulo que ficaram paradas em Pos-Vendas.

Antes do desvio 5 -> 10 existir, elas caiam na fase 6 e empilhavam la (40 caixas /
82 OS em 18/09/2026). O script as move para o Financeiro, que e' onde teriam parado
se o fluxo ja fosse o de hoje.
"""
import pytest

from app.core.config import settings
from app.models import Caixa, Cliente, Equipamento, EquipamentoCliente, LogOS, Ordem
from app.scripts.mover_phoebus_posvendas import caixas_alvo, processar


@pytest.fixture(autouse=True)
def _fases(fases_seed):
    """`caixas.fase` e `ordens.fase` sao FK para `fases` — sem o seed o INSERT morre."""


def _caixa(db, *, catalogo_id, fase=6, fase_os=None, cancelada=False):
    """Caixa na fase informada com 1 OS de um equipamento do catalogo `catalogo_id`."""
    cli = Cliente(nome=f"Cliente {catalogo_id}")
    eq = db.query(Equipamento).filter(Equipamento.id == catalogo_id).one_or_none()
    if eq is None:
        eq = Equipamento(id=catalogo_id, descricao=f"Equipamento {catalogo_id}")
        db.add(eq)
    db.add(cli); db.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie=f"S-{catalogo_id}")
    cx = Caixa(obs="Caixa backfill", fase=fase)
    db.add_all([ec, cx]); db.flush()
    o = Ordem(cliente=cli.id, equipamento_cliente=ec.id,
              fase=9 if cancelada else (fase_os if fase_os is not None else fase),
              situacao="C" if cancelada else "E", caixa=cx.id, desfecho_lab="concluido")
    db.add(o); db.commit(); db.refresh(cx)
    return cx.id, o.id


def test_caixas_alvo_pega_so_modulo_parado_em_posvendas(db_session):
    cx_id, _ = _caixa(db_session, catalogo_id=settings.EQUIPAMENTO_MODULO_ID)
    assert [c.id for c in caixas_alvo(db_session)] == [cx_id]


def test_caixas_alvo_ignora_caixa_comum_em_posvendas(db_session):
    """Controle positivo: caixa de aparelho normal em Pos-Vendas esta no lugar
    certo e nao pode ser movida."""
    _caixa(db_session, catalogo_id=1)
    assert caixas_alvo(db_session) == []


def test_caixas_alvo_ignora_modulo_em_outra_fase(db_session):
    """So a fase 6 e' alvo — caixa de modulo no laboratorio segue o fluxo normal
    e vai cair no Financeiro sozinha."""
    _caixa(db_session, catalogo_id=settings.EQUIPAMENTO_MODULO_ID, fase=5)
    assert caixas_alvo(db_session) == []


def test_simula_por_padrao_sem_gravar(db_session):
    cx_id, os_id = _caixa(db_session, catalogo_id=settings.EQUIPAMENTO_MODULO_ID)
    r = processar(db_session, aplicar=False)

    assert r["caixas"] == 1
    assert r["ordens"] == 1
    db_session.refresh(db_session.get(Caixa, cx_id))
    assert db_session.get(Caixa, cx_id).fase == 6      # nada gravado
    assert db_session.get(Ordem, os_id).fase == 6


def test_aplicar_move_caixa_e_os_para_o_financeiro(db_session):
    cx_id, os_id = _caixa(db_session, catalogo_id=settings.EQUIPAMENTO_MODULO_ID)
    r = processar(db_session, aplicar=True)

    assert r["caixas"] == 1 and r["ordens"] == 1
    assert db_session.get(Caixa, cx_id).fase == 10
    assert db_session.get(Ordem, os_id).fase == 10


def test_aplicar_nao_marca_aceite(db_session):
    """Mesma regra do fluxo novo: pular Pos-Vendas nao e' aprovar comercialmente.
    Por isso o script NAO passa por `executar_avanco_caixa` com origem=6, que
    marcaria `aceite=True` nas 82 OS."""
    _, os_id = _caixa(db_session, catalogo_id=settings.EQUIPAMENTO_MODULO_ID)
    processar(db_session, aplicar=True)

    o = db_session.get(Ordem, os_id)
    assert o.aceite is not True
    assert o.data_aceite is None


def test_aplicar_deixa_rastro_no_log_da_os(db_session):
    _, os_id = _caixa(db_session, catalogo_id=settings.EQUIPAMENTO_MODULO_ID)
    processar(db_session, aplicar=True)

    logs = db_session.query(LogOS).filter(LogOS.os == os_id).all()
    assert len(logs) == 1
    assert "6 -> 10" in logs[0].texto


def test_nao_mexe_em_os_cancelada_da_caixa(db_session):
    """OS cancelada mantem o vinculo com a caixa, mas nao anda de fase — so as
    ativas acompanham, igual ao fan-out de `executar_avanco_caixa`."""
    cx_id, os_ativa = _caixa(db_session, catalogo_id=settings.EQUIPAMENTO_MODULO_ID)
    cancelada = Ordem(cliente=db_session.get(Ordem, os_ativa).cliente,
                      fase=9, situacao="C", caixa=cx_id, desfecho_lab="concluido")
    db_session.add(cancelada); db_session.commit()

    r = processar(db_session, aplicar=True)

    assert r["ordens"] == 1                                  # so a ativa contou
    assert db_session.get(Ordem, cancelada.id).fase == 9     # cancelada intocada
    assert db_session.get(Ordem, os_ativa).fase == 10
    assert db_session.get(Caixa, cx_id).fase == 10


def test_caixa_mista_nao_e_alvo_do_backfill(db_session):
    """Caixa com Phoebus E aparelho normal fica de fora: mover em lote levaria o
    aparelho normal junto, pulando o Pos-Vendas que ele precisa. Ela ja esta na
    fase 6 e segue pela tela, 6 -> 10, com o aceite do Comercial.

    De proposito DIFERENTE do avanco em tempo real (`api/caixas.py`), que usa
    `caixa_de_modulo` (any) e desvia a caixa mista inteira: la existe alguem
    clicando e vendo o que faz; aqui sao 40 caixas de uma vez, sem ninguem olhando.
    """
    cx_id, os_phoebus = _caixa(db_session, catalogo_id=settings.EQUIPAMENTO_MODULO_ID)
    eq_normal = Equipamento(id=99, descricao="Iblow10 PRO")
    db_session.add(eq_normal); db_session.flush()
    ec = EquipamentoCliente(cliente=db_session.get(Ordem, os_phoebus).cliente,
                            equipamento=eq_normal.id, serie="WAO4O0200")
    db_session.add(ec); db_session.flush()
    db_session.add(Ordem(cliente=ec.cliente, equipamento_cliente=ec.id, fase=6,
                         situacao="E", caixa=cx_id, desfecho_lab="concluido"))
    db_session.commit()

    assert caixas_alvo(db_session) == []
    assert processar(db_session, aplicar=True)["caixas"] == 0
    assert db_session.get(Caixa, cx_id).fase == 6      # intocada


def test_caixa_so_com_os_cancelada_nao_e_alvo(db_session):
    """Sem nenhuma OS ativa nao ha o que mover — a caixa ja deveria estar
    arquivada. Mover so a caixa deixaria uma fase 10 vazia."""
    _caixa(db_session, catalogo_id=settings.EQUIPAMENTO_MODULO_ID, cancelada=True)
    assert caixas_alvo(db_session) == []


def test_idempotente_segunda_rodada_nao_acha_nada(db_session):
    _caixa(db_session, catalogo_id=settings.EQUIPAMENTO_MODULO_ID)
    processar(db_session, aplicar=True)

    assert caixas_alvo(db_session) == []
    assert processar(db_session, aplicar=True)["caixas"] == 0


def test_caixas_alvo_ignora_caixa_com_phoebus(db_session):
    """O aparelho gera servico e precisa do aceite comercial. Era o bug: com o
    criterio antigo (`any`) o backfill levou 7 caixas de Phoebus+Modulo ao
    Financeiro."""
    _caixa(db_session, catalogo_id=settings.EQUIPAMENTO_PHOEBUS_ID)
    assert caixas_alvo(db_session) == []


def test_caixas_alvo_ignora_caixa_de_phoebus_com_modulo(db_session):
    """A composicao real das 7: o par completo na mesma caixa."""
    cx_id, _ = _caixa(db_session, catalogo_id=settings.EQUIPAMENTO_PHOEBUS_ID)
    cx = db_session.get(Caixa, cx_id)
    cli = db_session.query(Cliente).first()
    eq = db_session.query(Equipamento).filter(
        Equipamento.id == settings.EQUIPAMENTO_MODULO_ID).one_or_none()
    if eq is None:
        eq = Equipamento(id=settings.EQUIPAMENTO_MODULO_ID, descricao="Modulo")
        db_session.add(eq); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="S-PAR-MOD")
    db_session.add(ec); db_session.flush()
    db_session.add(Ordem(cliente=cli.id, equipamento_cliente=ec.id, fase=cx.fase,
                         situacao="E", caixa=cx_id))
    db_session.commit()
    assert caixas_alvo(db_session) == []
