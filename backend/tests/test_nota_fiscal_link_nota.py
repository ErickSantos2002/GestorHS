"""Token do link publico por NOTA.

O formato antigo (`nf:{ordem_id}`) nao pode mudar: ha links ja publicados nos
cards do TaskHS. O novo nasce com prefixo proprio, ao lado dele.
"""
from app.core import nota_fiscal_link as l


def test_token_do_pdf_nao_abre_o_xml():
    tok = l.assinar_nota(7)
    assert l.verificar_nota(7, tok) is True
    assert l.verificar_nota(7, tok, l.XML) is False


def test_token_de_uma_nota_nao_abre_outra():
    assert l.verificar_nota(8, l.assinar_nota(7)) is False


def test_token_de_nota_nao_colide_com_o_de_ordem():
    """`nf:n:7` e `nf:7` sao mensagens distintas — um link de OS nao pode virar
    link de nota so porque os numeros batem."""
    assert l.verificar_nota(7, l.assinar(7)) is False
    assert l.verificar(7, l.assinar_nota(7)) is False


def test_link_da_nota_aponta_para_a_rota_publica(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "CERT_PUBLIC_BASE_URL", "https://gestor.hs/")
    assert l.link_nota(7).startswith("https://gestor.hs/publico/nota-fiscal/nota/7?t=")
    assert l.link_nota(7, l.XML).startswith("https://gestor.hs/publico/nota-fiscal/nota/7/xml?t=")


def test_sem_base_url_nao_ha_link(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "CERT_PUBLIC_BASE_URL", "")
    assert l.link_nota(7) is None
