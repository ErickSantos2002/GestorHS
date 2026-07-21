from app.models import LogIntegracao


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
