from app.core import emails


def test_normalizar_trim_e_lowercase():
    assert emails.normalizar("  Admin@HS.com  ") == "admin@hs.com"


def test_normalizar_vazio_ou_none():
    assert emails.normalizar("") == ""
    assert emails.normalizar(None) == ""
