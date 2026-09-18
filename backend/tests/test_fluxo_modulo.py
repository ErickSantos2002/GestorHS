from types import SimpleNamespace

from app.core import fluxo_modulo
from app.core.config import settings


def _os(catalogo):
    """OS fake: o predicado só olha `equipamento_catalogo`."""
    return SimpleNamespace(id=1, equipamento_catalogo=catalogo)


def test_os_de_modulo_reconhece_modulo_e_phoebus():
    assert fluxo_modulo.os_de_modulo(_os(settings.EQUIPAMENTO_MODULO_ID)) is True
    assert fluxo_modulo.os_de_modulo(_os(settings.EQUIPAMENTO_PHOEBUS_ID)) is True


def test_os_de_modulo_ignora_equipamento_comum():
    assert fluxo_modulo.os_de_modulo(_os(1)) is False


def test_os_de_modulo_sem_equipamento_nao_bloqueia():
    assert fluxo_modulo.os_de_modulo(_os(None)) is False


def test_os_de_modulo_modulo_ebs_nao_bloqueia():
    """Decisao de escopo: o Modulo de Calibracao para EBS (catalogo 49) e o EBS (37)
    NAO entram na regra. Este teste trava a decisao."""
    assert fluxo_modulo.os_de_modulo(_os(49)) is False
    assert fluxo_modulo.os_de_modulo(_os(37)) is False


def test_caixa_de_modulo_qualquer_os_contamina():
    ordens = [_os(1), _os(settings.EQUIPAMENTO_MODULO_ID), _os(1)]
    assert fluxo_modulo.caixa_de_modulo(ordens) is True


def test_caixa_de_modulo_so_comuns_nao_bloqueia():
    assert fluxo_modulo.caixa_de_modulo([_os(1), _os(2)]) is False


def test_caixa_de_modulo_lista_vazia_nao_bloqueia():
    assert fluxo_modulo.caixa_de_modulo([]) is False


def test_equipamentos_de_modulo_le_settings_na_chamada(monkeypatch):
    """O conjunto e' lido a cada chamada — um set de modulo congelaria o valor no
    import e furaria o monkeypatch (e qualquer override por env)."""
    monkeypatch.setattr(settings, "EQUIPAMENTO_MODULO_ID", 999)
    assert 999 in fluxo_modulo.equipamentos_de_modulo()
    assert fluxo_modulo.os_de_modulo(_os(999)) is True


def test_equipamento_catalogo_na_ordem(db_session, os_base, fases_seed):
    """A property e' a ponte entre a OS e o predicado: id de catalogo do equipamento."""
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"],
              equipamento_cliente=os_base["equipamento_cliente"],
              fase=4, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    assert o.equipamento_catalogo == os_base["equipamento"]


def test_equipamento_catalogo_none_sem_equipamento(db_session, os_base, fases_seed):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=None, fase=4, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    assert o.equipamento_catalogo is None


# --- rotulo para o aviso do Financeiro (set/2026) ---

def test_rotulo_so_phoebus():
    assert fluxo_modulo.rotulo_modulo([_os(settings.EQUIPAMENTO_PHOEBUS_ID)]) == "phoebus"


def test_rotulo_so_modulo():
    assert fluxo_modulo.rotulo_modulo([_os(settings.EQUIPAMENTO_MODULO_ID)]) == "modulo"


def test_rotulo_os_dois_juntos():
    """O caso mais comum no Financeiro hoje (7 das 8 caixas): o aparelho e o modulo
    dele viajam na mesma caixa."""
    ordens = [_os(settings.EQUIPAMENTO_PHOEBUS_ID), _os(settings.EQUIPAMENTO_MODULO_ID)]
    assert fluxo_modulo.rotulo_modulo(ordens) == "ambos"


def test_rotulo_ignora_aparelho_comum_junto():
    """Caixa mista: o aviso e' sobre o que tem de Phoebus/modulo, e o aparelho comum
    nao muda o rotulo."""
    ordens = [_os(1), _os(settings.EQUIPAMENTO_PHOEBUS_ID)]
    assert fluxo_modulo.rotulo_modulo(ordens) == "phoebus"


def test_rotulo_none_sem_phoebus_nem_modulo():
    assert fluxo_modulo.rotulo_modulo([_os(1), _os(2)]) is None
    assert fluxo_modulo.rotulo_modulo([]) is None


def test_desvio_implica_rotulo_de_modulo():
    """Antes era EQUIVALENCIA (`rotulo is not None` == `caixa_de_modulo`). Agora e'
    IMPLICACAO, nos dois sentidos uteis: quem desvia tem rotulo 'modulo' e tem card
    bloqueado. Ter rotulo NAO implica desviar — Phoebus+Modulo tem rotulo 'ambos' e
    segue pelo Pos-Vendas. Se a implicacao quebrar, o Financeiro passa a ver um badge
    que nao explica a fase em que a caixa esta."""
    casos = [[], [_os(1)], [_os(settings.EQUIPAMENTO_PHOEBUS_ID)],
             [_os(settings.EQUIPAMENTO_MODULO_ID)],
             [_os(1), _os(settings.EQUIPAMENTO_MODULO_ID)],
             [_os(settings.EQUIPAMENTO_PHOEBUS_ID), _os(settings.EQUIPAMENTO_MODULO_ID)]]
    for ordens in casos:
        if fluxo_modulo.caixa_pula_posvendas(ordens):
            assert fluxo_modulo.rotulo_modulo(ordens) == "modulo"
            assert fluxo_modulo.caixa_de_modulo(ordens) is True


# --- quem pula o Pos-Vendas (correcao de 18/09/2026) ---

def test_pula_posvendas_so_modulo():
    """A UNICA composicao que nao passa pelo comercial: servico de bancada."""
    assert fluxo_modulo.caixa_pula_posvendas([_os(settings.EQUIPAMENTO_MODULO_ID)]) is True
    assert fluxo_modulo.caixa_pula_posvendas(
        [_os(settings.EQUIPAMENTO_MODULO_ID), _os(settings.EQUIPAMENTO_MODULO_ID)]) is True


def test_pula_posvendas_phoebus_com_modulo_nao_pula():
    """O bug: o par completo gera servico e precisa do aceite comercial. Sao 22 caixas
    na base, e no TaskHS elas param em 'LIBERADOS DO LABORATORIO', antes da lista
    'Servicos' — nao chegaram nem perto do Financeiro."""
    ordens = [_os(settings.EQUIPAMENTO_PHOEBUS_ID), _os(settings.EQUIPAMENTO_MODULO_ID)]
    assert fluxo_modulo.caixa_pula_posvendas(ordens) is False


def test_pula_posvendas_so_phoebus_nao_pula():
    """O aparelho sozinho tambem gera servico — decidido em 18/09/2026."""
    assert fluxo_modulo.caixa_pula_posvendas([_os(settings.EQUIPAMENTO_PHOEBUS_ID)]) is False


def test_pula_posvendas_mista_nao_pula():
    """Caixa mista cai fora por CONSTRUCAO. Antes precisava de um `all` separado no
    backfill para nao arrastar o aparelho normal; agora a regra ja exclui."""
    assert fluxo_modulo.caixa_pula_posvendas(
        [_os(1), _os(settings.EQUIPAMENTO_MODULO_ID)]) is False


def test_pula_posvendas_lista_vazia():
    """Caixa sem OS ativa nao tem para onde desviar."""
    assert fluxo_modulo.caixa_pula_posvendas([]) is False


def test_pula_posvendas_le_settings_na_chamada(monkeypatch):
    """Mesmo motivo de `equipamentos_de_modulo`: valor congelado no import furaria o
    override por env e o monkeypatch."""
    monkeypatch.setattr(settings, "EQUIPAMENTO_MODULO_ID", 999)
    assert fluxo_modulo.caixa_pula_posvendas([_os(999)]) is True


# --- nucleo compartilhado das duas decisoes (set/2026) ---

def test_so_de_modulo_reconhece_caixa_100_por_cento_modulo():
    assert fluxo_modulo.caixa_so_de_modulo([_os(settings.EQUIPAMENTO_MODULO_ID)]) is True
    assert fluxo_modulo.caixa_so_de_modulo(
        [_os(settings.EQUIPAMENTO_MODULO_ID), _os(settings.EQUIPAMENTO_MODULO_ID)]) is True


def test_so_de_modulo_recusa_phoebus_em_qualquer_composicao():
    """Phoebus sozinho, com o modulo dele, ou com aparelho comum: nenhuma e' 100% Modulo."""
    assert fluxo_modulo.caixa_so_de_modulo([_os(settings.EQUIPAMENTO_PHOEBUS_ID)]) is False
    assert fluxo_modulo.caixa_so_de_modulo(
        [_os(settings.EQUIPAMENTO_PHOEBUS_ID), _os(settings.EQUIPAMENTO_MODULO_ID)]) is False
    assert fluxo_modulo.caixa_so_de_modulo(
        [_os(settings.EQUIPAMENTO_PHOEBUS_ID), _os(1)]) is False


def test_so_de_modulo_recusa_mista_e_vazia():
    assert fluxo_modulo.caixa_so_de_modulo([_os(1), _os(settings.EQUIPAMENTO_MODULO_ID)]) is False
    assert fluxo_modulo.caixa_so_de_modulo([_os(1)]) is False
    assert fluxo_modulo.caixa_so_de_modulo([]) is False


def test_pula_posvendas_e_so_de_modulo_sao_a_MESMA_resposta():
    """As duas decisoes (pular o Pos-Vendas, ficar fora do board do TaskHS) partem do
    mesmo criterio. Se divergirem, uma copia do predicado foi introduzida."""
    casos = [[], [_os(1)], [_os(settings.EQUIPAMENTO_MODULO_ID)],
             [_os(settings.EQUIPAMENTO_PHOEBUS_ID)],
             [_os(settings.EQUIPAMENTO_PHOEBUS_ID), _os(settings.EQUIPAMENTO_MODULO_ID)],
             [_os(1), _os(settings.EQUIPAMENTO_MODULO_ID)]]
    for ordens in casos:
        assert fluxo_modulo.caixa_pula_posvendas(ordens) == fluxo_modulo.caixa_so_de_modulo(ordens)
