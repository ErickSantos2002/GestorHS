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
