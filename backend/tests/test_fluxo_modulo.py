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


def test_rotulo_concorda_com_caixa_de_modulo():
    """Os dois respondem a mesma pergunta por caminhos diferentes — se divergirem, o
    aviso aparece onde o fluxo nao desvia (ou o contrario), que e' o pior dos mundos."""
    casos = [[], [_os(1)], [_os(settings.EQUIPAMENTO_PHOEBUS_ID)],
             [_os(settings.EQUIPAMENTO_MODULO_ID)],
             [_os(1), _os(settings.EQUIPAMENTO_MODULO_ID)]]
    for ordens in casos:
        assert (fluxo_modulo.rotulo_modulo(ordens) is not None) == fluxo_modulo.caixa_de_modulo(ordens)
