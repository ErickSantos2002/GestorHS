from app.models import Cliente


def test_cliente_nasce_sem_estado_do_tiny(db_session):
    c = Cliente(nome="ACME", cgc="08857492000148")
    db_session.add(c); db_session.commit(); db_session.refresh(c)
    assert c.tiny_id is None and c.tiny_status is None
    assert c.tiny_erro is None and c.tiny_em is None


def test_listagem_e_detalhe_expoem_o_estado_do_tiny(client_comercial, db_session):
    c = Cliente(nome="ACME", cgc="08857492000148", tiny_id=610662219,
                tiny_status="enviada", tiny_erro=None)
    db_session.add(c); db_session.commit()

    item = client_comercial.get("/clientes").json()["items"][0]
    assert item["tiny_id"] == 610662219 and item["tiny_status"] == "enviada"
    assert item["tiny_erro"] is None

    detalhe = client_comercial.get(f"/clientes/{c.id}").json()
    assert detalhe["tiny_id"] == 610662219 and detalhe["tiny_status"] == "enviada"
