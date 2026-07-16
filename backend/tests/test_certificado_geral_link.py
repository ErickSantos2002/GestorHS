from app.core import certificado_geral_link as link


def test_assinar_e_verificar_roundtrip():
    t = link.assinar(7)
    assert link.verificar(7, t) is True


def test_token_adulterado_ou_de_outro_id_falha():
    t = link.assinar(7)
    assert link.verificar(8, t) is False        # id diferente
    assert link.verificar(7, t + "x") is False  # token adulterado
    assert link.verificar(7, None) is False


def test_link_none_quando_base_vazia(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "CERT_PUBLIC_BASE_URL", "")
    assert link.link_certificado_geral(7) is None


def test_link_montado_com_base(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "CERT_PUBLIC_BASE_URL", "https://x.com/")
    url = link.link_certificado_geral(7)
    assert url is not None
    assert url.startswith("https://x.com/publico/certificado-geral/7?t=")
