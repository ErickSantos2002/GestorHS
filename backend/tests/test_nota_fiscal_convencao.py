from app.core import nota_fiscal


def test_subdir_por_os():
    assert nota_fiscal.subdir(7) == "notas-fiscais/7"


def test_media_type_por_extensao():
    assert nota_fiscal.media_type("abc.pdf") == "application/pdf"
    assert nota_fiscal.media_type("abc.xml") == "application/xml"
    assert nota_fiscal.media_type("ABC.XML") == "application/xml"   # case-insensitive
    assert nota_fiscal.media_type("sem-extensao") == "application/pdf"  # default
