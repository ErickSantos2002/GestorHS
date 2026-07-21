from app.models import LogIntegracao
from app.integrations.log_integracao import registrar_log_integracao


def test_modelo_insere_linha(db_session):
    row = LogIntegracao(
        integracao="growthhs", tipo="os_card", external_id="10853",
        referencia_os=10853, status="sucesso", http_status=200,
        resposta="ok", payload={"source": "gestorhs.os", "external_id": "10853"},
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    assert row.id is not None
    assert row.criado_em is not None
    assert row.payload["external_id"] == "10853"


def test_writer_grava_linha_com_db_injetado(db_session):
    registrar_log_integracao(
        integracao="growthhs", status="sucesso", http_status=200, resposta="ok",
        payload={"source": "gestorhs.os", "external_id": "10853"}, db=db_session,
    )
    row = db_session.query(LogIntegracao).one()
    assert row.integracao == "growthhs"
    assert row.tipo == "os_card"
    assert row.external_id == "10853"
    assert row.referencia_os == 10853
    assert row.status == "sucesso"


def test_writer_trunca_resposta(db_session):
    registrar_log_integracao(
        integracao="taskhs", status="erro", resposta="x" * 5000,
        payload={"source": "gestorhs", "external_id": "1"}, db=db_session,
    )
    row = db_session.query(LogIntegracao).one()
    assert len(row.resposta) == 2000


def test_writer_nunca_levanta(db_session):
    registrar_log_integracao(integracao="growthhs", status="pulado",
                             motivo="desligado", payload=None, db=db_session)
    assert db_session.query(LogIntegracao).count() == 1
