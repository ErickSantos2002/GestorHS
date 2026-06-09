def test_schemas_basicos():
    from app.schemas.certificados_modelo import (
        ModeloItem, CertificadoModeloOut, CertificadoModeloIn, ImagemOut,
    )
    item = ModeloItem(equipamento=3, equipamento_descricao="Mark X", tem_calibracao=True)
    assert item.tem_calibracao is True
    assert item.tem_manutencao is False
    out = CertificadoModeloOut(equipamento=3, equipamento_descricao="Mark X", tipo="C", descricao="d", texto="<p>x</p>")
    assert out.texto == "<p>x</p>"
    assert out.tipo == "C"
    inp = CertificadoModeloIn(texto="<p>y</p>")
    assert inp.descricao is None and inp.texto == "<p>y</p>"
    img = ImagemOut(id=1, nome="Logo", arquivo="a.png", url="/certificado-imagens/arquivo/a.png")
    assert img.url.endswith("a.png")
