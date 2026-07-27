from datetime import date, timedelta

import pytest

from app.core.config import settings
from app.models import Cliente, Equipamento, EquipamentoCliente
from app.scripts.enviar_vencendo_growthhs import (
    agrupar_por_cliente,
    buscar_excluidos_por_os,
    buscar_vencendo,
    competencias_padrao,
)

HOJE = date.today()
# Competencia de teste: o mes que vem inteiro esta SEMPRE no futuro em relacao a
# `date.today()`, entao o `max(hoje, primeiro dia do mes)` do filtro nunca corta nada
# e o teste nao muda de resultado conforme o dia em que roda.
MES_QUE_VEM = (HOJE.replace(day=1) + timedelta(days=32)).replace(day=1)
MES_SEGUINTE = (MES_QUE_VEM + timedelta(days=32)).replace(day=1)
ULTIMO_DIA_DO_MES_QUE_VEM = MES_SEGUINTE - timedelta(days=1)


# IDs explicitos e ACIMA de `CLIENTE_ESTOQUE_HS_ID` (2): com id auto-incrementado o
# segundo cliente caia justamente no 2 e era descartado pelo filtro de estoque interno,
# fazendo o teste de agrupamento falhar por um motivo que nao tem nada a ver com ele.
# A ordem 101 < 102 tambem e' a que o teste de agrupamento espera.
@pytest.fixture
def cliente(db_session):
    c = Cliente(id=101, nome="ACME Ltda")
    db_session.add(c); db_session.commit(); db_session.refresh(c)
    return c


@pytest.fixture
def outro_cliente(db_session):
    c = Cliente(id=102, nome="Beta SA")
    db_session.add(c); db_session.commit(); db_session.refresh(c)
    return c


@pytest.fixture
def equipamentos(db_session):
    """O conftest liga `PRAGMA foreign_keys=ON`, entao `equipamentos_cliente.equipamento`
    PRECISA apontar para uma linha real de `equipamentos` — inclusive os IDs de exclusao
    (Phoebus 36 / EBS 37), que sao criados aqui com ID explicito para os testes de filtro."""
    linhas = {
        "modulo": Equipamento(id=settings.EQUIPAMENTO_MODULO_ID, descricao="Modulo de calibracao"),
        "phoebus": Equipamento(id=settings.EQUIPAMENTO_PHOEBUS_ID, descricao="Phoebus"),
        "ebs": Equipamento(id=settings.EQUIPAMENTO_EBS_ID, descricao="EBS"),
    }
    db_session.add_all(linhas.values()); db_session.commit()
    return {nome: eq.id for nome, eq in linhas.items()}


def _ec(db_session, cliente_id, *, vence, equipamento=None, ativo=True, os_atual=None):
    ec = EquipamentoCliente(
        cliente=cliente_id,
        equipamento=equipamento if equipamento is not None else settings.EQUIPAMENTO_MODULO_ID,
        serie=f"SN-{vence.isoformat()}",
        prox_calibragem=vence, ativo=ativo, os_atual=os_atual,
    )
    db_session.add(ec); db_session.commit(); db_session.refresh(ec)
    return ec


def _ids(linhas):
    return {linha["ec"].id for linha in linhas}


def _dia(n):
    """Dia `n` do mes de teste."""
    return MES_QUE_VEM.replace(day=n)


# ---------------------------------------------------------------------------
# Selecao por competencia
# ---------------------------------------------------------------------------

def test_pega_dentro_da_competencia(db_session, cliente, equipamentos):
    dentro = _ec(db_session, cliente.id, vence=_dia(10))
    assert dentro.id in _ids(buscar_vencendo(db_session, MES_QUE_VEM))


def test_inclui_as_duas_bordas_do_mes(db_session, cliente, equipamentos):
    """Janela FECHADA nos dois lados: dia 1 entra, ultimo dia do mes entra."""
    primeiro = _ec(db_session, cliente.id, vence=_dia(1))
    ultimo = _ec(db_session, cliente.id, vence=ULTIMO_DIA_DO_MES_QUE_VEM)
    ids = _ids(buscar_vencendo(db_session, MES_QUE_VEM))
    assert primeiro.id in ids
    assert ultimo.id in ids


def test_ignora_o_mes_seguinte(db_session, cliente, equipamentos):
    """Cada competencia e' um card diferente; misturar meses quebraria a chave."""
    proximo = _ec(db_session, cliente.id, vence=MES_SEGUINTE)
    assert proximo.id not in _ids(buscar_vencendo(db_session, MES_QUE_VEM))


def test_ignora_vencidos(db_session, cliente, equipamentos):
    """Vencido e' backlog da Etapa 1 — incluir aqui geraria milhares de cards
    num formato diferente do que a Etapa 1 ja criou."""
    vencido = _ec(db_session, cliente.id, vence=HOJE - timedelta(days=1))
    assert vencido.id not in _ids(buscar_vencendo(db_session, HOJE.replace(day=1)))


def test_ignora_com_os_em_andamento(db_session, cliente, equipamentos):
    """Se o cliente ja mandou o aparelho, 'entre em contato' e' ruido."""
    em_os = _ec(db_session, cliente.id, vence=_dia(10), os_atual=12345)
    assert em_os.id not in _ids(buscar_vencendo(db_session, MES_QUE_VEM))


def test_ignora_inativo(db_session, cliente, equipamentos):
    inativo = _ec(db_session, cliente.id, vence=_dia(10), ativo=False)
    assert inativo.id not in _ids(buscar_vencendo(db_session, MES_QUE_VEM))


def test_ignora_phoebus_e_ebs(db_session, cliente, equipamentos):
    """Sao hospedeiros: nao sao calibrados, quem calibra e' o modulo dentro deles."""
    ph = _ec(db_session, cliente.id, vence=_dia(10),
             equipamento=settings.EQUIPAMENTO_PHOEBUS_ID)
    ebs = _ec(db_session, cliente.id, vence=_dia(11),
              equipamento=settings.EQUIPAMENTO_EBS_ID)
    ids = _ids(buscar_vencendo(db_session, MES_QUE_VEM))
    assert ph.id not in ids
    assert ebs.id not in ids


def test_ignora_cliente_de_estoque_interno(db_session, equipamentos):
    estoque = Cliente(id=settings.CLIENTE_ESTOQUE_HS_ID, nome="Estoque HS")
    db_session.add(estoque); db_session.commit()
    ec = _ec(db_session, settings.CLIENTE_ESTOQUE_HS_ID, vence=_dia(10))
    assert ec.id not in _ids(buscar_vencendo(db_session, MES_QUE_VEM))


# ---------------------------------------------------------------------------
# Agrupamento (puro)
# ---------------------------------------------------------------------------

def test_agrupa_por_cliente_e_ordena_por_vencimento(db_session, cliente, outro_cliente,
                                                    equipamentos):
    a2 = _ec(db_session, cliente.id, vence=_dia(20))
    a1 = _ec(db_session, cliente.id, vence=_dia(3))
    b1 = _ec(db_session, outro_cliente.id, vence=_dia(9))

    grupos = agrupar_por_cliente(buscar_vencendo(db_session, MES_QUE_VEM))

    assert [[l["ec"].id for l in g] for g in grupos] == [[a1.id, a2.id], [b1.id]]


def test_agrupar_lista_vazia():
    assert agrupar_por_cliente([]) == []


# ---------------------------------------------------------------------------
# Excluidos por OS — so entram no relatorio, nunca viram card
# ---------------------------------------------------------------------------

def test_excluidos_por_os_lista_quem_ficou_de_fora(db_session, cliente, equipamentos):
    em_os = _ec(db_session, cliente.id, vence=_dia(10), os_atual=10902)
    _ec(db_session, cliente.id, vence=_dia(11))
    excluidos = buscar_excluidos_por_os(db_session, MES_QUE_VEM)
    assert _ids(excluidos) == {em_os.id}


def test_excluidos_respeita_os_demais_filtros(db_session, cliente, equipamentos):
    inativo_em_os = _ec(db_session, cliente.id, vence=_dia(10), os_atual=1, ativo=False)
    assert inativo_em_os.id not in _ids(buscar_excluidos_por_os(db_session, MES_QUE_VEM))


# ---------------------------------------------------------------------------
# Competencias padrao
# ---------------------------------------------------------------------------

def test_competencias_padrao_sao_o_mes_corrente_e_o_seguinte():
    assert competencias_padrao(date(2026, 8, 14)) == [date(2026, 8, 1), date(2026, 9, 1)]


def test_competencias_padrao_viram_o_ano():
    assert competencias_padrao(date(2026, 12, 3)) == [date(2026, 12, 1), date(2027, 1, 1)]
