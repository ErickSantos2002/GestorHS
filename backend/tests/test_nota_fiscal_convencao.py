from app.core import nota_fiscal


def test_subdir_por_os():
    assert nota_fiscal.subdir(7) == "notas-fiscais/7"


def test_media_type_por_extensao():
    assert nota_fiscal.media_type("abc.pdf") == "application/pdf"
    # XML e conteudo de usuario: nunca renderizado inline (evita XSS via polyglot XML/XHTML)
    assert nota_fiscal.media_type("abc.xml") == "application/octet-stream"
    assert nota_fiscal.media_type("ABC.XML") == "application/octet-stream"   # case-insensitive
    assert nota_fiscal.media_type("sem-extensao") == "application/pdf"  # default


def test_nome_download_por_extensao():
    assert nota_fiscal.nome_download(7, "abc.pdf") == "nota-fiscal-7.pdf"
    assert nota_fiscal.nome_download(7, "abc.xml") == "nota-fiscal-7.xml"
    assert nota_fiscal.nome_download(7, "ABC.XML") == "nota-fiscal-7.xml"
    assert nota_fiscal.nome_download(7, "sem-extensao") == "nota-fiscal-7.pdf"
