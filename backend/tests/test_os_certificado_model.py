def test_certificado_modelo_tipo_default(db_session):
    from app.models import Equipamento, CertificadoModelo
    eq = Equipamento(descricao="Mark X")
    db_session.add(eq); db_session.flush()
    c = CertificadoModelo(equipamento=eq.id, texto="<p>x</p>")
    db_session.add(c); db_session.commit(); db_session.refresh(c)
    assert c.tipo == "C"


def test_certificado_modelo_dois_tipos(db_session):
    from app.models import Equipamento, CertificadoModelo
    eq = Equipamento(descricao="Mark X")
    db_session.add(eq); db_session.flush()
    db_session.add(CertificadoModelo(equipamento=eq.id, tipo="C", texto="<p>cal</p>"))
    db_session.add(CertificadoModelo(equipamento=eq.id, tipo="M", texto="<p>man</p>"))
    db_session.commit()
    from app.models import CertificadoModelo as CM
    assert db_session.query(CM).filter_by(equipamento=eq.id).count() == 2


def test_os_certificado_model(db_session):
    from app.models import Cliente, Ordem, OSCertificado
    cli = Cliente(nome="C"); db_session.add(cli); db_session.flush()
    o = Ordem(cliente=cli.id, situacao="E"); db_session.add(o); db_session.flush()
    osc = OSCertificado(os=o.id, tipo="C", html="<p>oi</p>")
    db_session.add(osc); db_session.commit(); db_session.refresh(osc)
    assert osc.tipo == "C" and osc.html == "<p>oi</p>"
