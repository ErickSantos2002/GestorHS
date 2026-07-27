def test_caixa_cliente_principal(db_session, fases_seed):
    from app.models import Cliente, Caixa
    cli = Cliente(nome="ACME"); db_session.add(cli); db_session.flush()
    cx = Caixa(fase=4, cliente_principal=cli.id); db_session.add(cx); db_session.flush()
    db_session.refresh(cx)
    assert cx.cliente_principal == cli.id
    assert cx.cliente_principal_nome == "ACME"


def test_vincular_os_de_outro_cliente_agora_permite(client_exp, caixa_com_os_cliente_a, os_cliente_b):
    r = client_exp.post(f"/caixas/{caixa_com_os_cliente_a}/ordens", json={"ordem_id": os_cliente_b})
    assert r.status_code == 200  # antes era 409


def test_abrir_os_com_caixa_de_outro_cliente_agora_permite(client_exp, caixa_com_os_cliente_a, os_base):
    r = client_exp.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"],
        "tipo_servico": "C",
        "caixa": caixa_com_os_cliente_a,
    })
    assert r.status_code == 201  # antes era 409
