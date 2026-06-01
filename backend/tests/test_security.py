from app.core.security import hash_senha, verificar_senha


def test_hash_difere_do_texto_puro():
    h = hash_senha("minhaSenha123")
    assert h != "minhaSenha123"
    assert len(h) > 20


def test_verificar_senha_correta_e_incorreta():
    h = hash_senha("minhaSenha123")
    assert verificar_senha("minhaSenha123", h) is True
    assert verificar_senha("errada", h) is False
