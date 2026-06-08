def test_certificado_modelo_props(db_session):
    from app.models import Equipamento, CertificadoModelo
    eq = Equipamento(descricao="Bafômetro Mark X")
    db_session.add(eq); db_session.flush()
    c = CertificadoModelo(equipamento=eq.id, descricao="Cert Mark X", texto="<p>oi</p>")
    db_session.add(c); db_session.commit(); db_session.refresh(c)
    assert c.equipamento_descricao == "Bafômetro Mark X"
    assert c.texto == "<p>oi</p>"


def test_certificado_imagem_url(db_session):
    from app.models import CertificadoImagem
    img = CertificadoImagem(arquivo="abc123.png", nome="Logo")
    db_session.add(img); db_session.commit(); db_session.refresh(img)
    assert img.url == "/certificado-imagens/arquivo/abc123.png"
