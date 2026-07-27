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


def test_avancar_recebido_um_cliente_auto_define_principal(client_exp, caixa_recebido_um_cliente):
    r = client_exp.post(f"/caixas/{caixa_recebido_um_cliente}/avancar", json={})
    assert r.status_code == 200
    assert r.json()["cliente_principal"] is not None


def test_avancar_recebido_multi_sem_principal_bloqueia(client_exp, caixa_recebido_dois_clientes):
    r = client_exp.post(f"/caixas/{caixa_recebido_dois_clientes}/avancar", json={})
    assert r.status_code == 409
    assert "principal" in r.json()["detail"].lower()


def test_avancar_recebido_multi_com_principal_valido(client_exp, caixa_recebido_dois_clientes, cliente_a_id):
    r = client_exp.post(f"/caixas/{caixa_recebido_dois_clientes}/avancar", json={"cliente_principal": cliente_a_id})
    assert r.status_code == 200
    assert r.json()["cliente_principal"] == cliente_a_id


def test_avancar_recebido_principal_fora_da_caixa_falha(client_exp, caixa_recebido_dois_clientes, cliente_externo_id):
    r = client_exp.post(f"/caixas/{caixa_recebido_dois_clientes}/avancar", json={"cliente_principal": cliente_externo_id})
    assert r.status_code == 409


def test_card_caixa_usa_cliente_principal(monkeypatch, db_session, caixa_multi_com_principal_b):
    # caixa com OS do cliente A (1a) e B, cliente_principal = B
    import app.api.growthhs_cards as gc
    enviados = []
    monkeypatch.setattr(gc.hsgrowth_client, "integracao_ativa", lambda: True)
    monkeypatch.setattr(gc.hsgrowth_client, "enviar_card", lambda card: enviados.append(card))
    from fastapi import BackgroundTasks
    bt = BackgroundTasks()
    gc.agendar_card_caixa(db_session, bt, caixa_multi_com_principal_b)
    for t in bt.tasks: t.func(*t.args, **t.kwargs)
    assert enviados and enviados[0]["client"]["name"] == "CLIENTE B"
