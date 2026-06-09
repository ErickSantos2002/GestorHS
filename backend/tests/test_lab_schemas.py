def test_gerar_certificado_in():
    from app.schemas.ordens import GerarCertificadoIn
    m = GerarCertificadoIn(tipo_calibragem=2, calib_cert="C-1", calib_temp="25",
                           calib_pressao="1", calib_teste1="a", calib_teste2="b",
                           calib_teste3="c", calib_teste_media="0,20", calib_situacao="Aprovado")
    assert m.calib_cert == "C-1" and m.tipo_calibragem == 2


def test_avancar_in_sem_calib():
    from app.schemas.ordens import AvancarIn
    m = AvancarIn(obs="x")
    assert not hasattr(m, "calib_cert")
    assert not hasattr(m, "calib_teste1")
    assert not hasattr(m, "pdf_certificado")
    assert m.obs == "x"
    m2 = AvancarIn(prox_calibragem=None, cod_retorno=None)
    assert m2.prox_calibragem is None


def test_ordem_out_expoe_calib_para_prefill(db_session):
    from app.models import Cliente, Ordem
    from app.schemas.ordens import OrdemOut
    cli = Cliente(nome="C"); db_session.add(cli); db_session.flush()
    o = Ordem(cliente=cli.id, situacao="E", tipo_calibragem=3,
              calib_teste1="a", calib_teste2="b", calib_teste3="c")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    out = OrdemOut.model_validate(o)
    assert out.tipo_calibragem == 3
    assert out.calib_teste1 == "a" and out.calib_teste2 == "b" and out.calib_teste3 == "c"
