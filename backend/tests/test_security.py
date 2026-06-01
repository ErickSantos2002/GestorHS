from app.core.security import hash_senha, verificar_senha


def test_hash_difere_do_texto_puro():
    h = hash_senha("minhaSenha123")
    assert h != "minhaSenha123"
    assert len(h) > 20


def test_verificar_senha_correta_e_incorreta():
    h = hash_senha("minhaSenha123")
    assert verificar_senha("minhaSenha123", h) is True
    assert verificar_senha("errada", h) is False


import pytest
from jose import JWTError
from app.core.security import criar_access_token, criar_refresh_token, decodificar_token


def test_access_token_roundtrip():
    token = criar_access_token(sub="42", tipo="usuario")
    dados = decodificar_token(token)
    assert dados["sub"] == "42"
    assert dados["tipo"] == "usuario"
    assert dados["token_use"] == "access"


def test_refresh_token_marca_uso():
    token = criar_refresh_token(sub="7", tipo="cliente")
    dados = decodificar_token(token)
    assert dados["token_use"] == "refresh"
    assert dados["tipo"] == "cliente"


def test_token_invalido_levanta_erro():
    with pytest.raises(JWTError):
        decodificar_token("nao-e-um-token")
