from app.core.caixa import contar_outros, principal_valido, cliente_unico


def test_contar_outros():
    assert contar_outros([]) == 0
    assert contar_outros([7]) == 0
    assert contar_outros([7, 7]) == 0            # mesmo cliente, 2 OS
    assert contar_outros([7, 9]) == 1
    assert contar_outros([7, 9, 9, None]) == 1   # ignora None e repetidos


def test_principal_valido():
    assert principal_valido(7, [7, 9]) == 7
    assert principal_valido(5, [7, 9]) is None   # stale
    assert principal_valido(None, [7]) is None


def test_cliente_unico():
    assert cliente_unico([7, 7]) == 7
    assert cliente_unico([]) is None
    assert cliente_unico([7, 9]) is None
    assert cliente_unico([None, 7, 7]) == 7


def test_ordens_do_card_exclui_canceladas():
    from types import SimpleNamespace
    from app.core.caixa import ordens_do_card
    ativa, cancelada = SimpleNamespace(id=1, fase=6), SimpleNamespace(id=2, fase=9)
    cx = SimpleNamespace(ordens=[ativa, cancelada])
    assert ordens_do_card(cx) == [ativa]


def test_ordens_do_card_caixa_toda_cancelada_cai_na_lista_completa():
    """Sem o fallback, uma caixa 100% cancelada devolveria lista vazia e o card
    ficaria sem nenhuma OS."""
    from types import SimpleNamespace
    from app.core.caixa import ordens_do_card
    a, b = SimpleNamespace(id=1, fase=9), SimpleNamespace(id=2, fase=9)
    cx = SimpleNamespace(ordens=[a, b])
    assert ordens_do_card(cx) == [a, b]


def test_ordens_do_card_caixa_vazia():
    from types import SimpleNamespace
    from app.core.caixa import ordens_do_card
    assert ordens_do_card(SimpleNamespace(ordens=[])) == []
