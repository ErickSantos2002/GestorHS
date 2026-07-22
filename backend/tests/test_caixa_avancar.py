def test_avancar_e_cancelar_per_os_devolvem_409(client_lab, os_no_lab):
    """A OS nao anda mais sozinha: os endpoints per-OS `/ordens/{id}/avancar` e
    `/ordens/{id}/cancelar` sao deprecados em favor de `/caixas/{id}/avancar` e
    `/caixas/{id}/cancelar` — quem chamar o caminho antigo recebe 409."""
    r_avancar = client_lab.post(f"/ordens/{os_no_lab}/avancar", json={})
    assert r_avancar.status_code == 409

    r_cancelar = client_lab.post(f"/ordens/{os_no_lab}/cancelar", json={"motivo": "teste"})
    assert r_cancelar.status_code == 409


def test_marcar_sem_conserto_exige_obs(client_lab, os_no_lab):
    r = client_lab.post(f"/ordens/{os_no_lab}/desfecho-lab",
                        json={"desfecho": "sem_conserto", "obs": ""})
    assert r.status_code == 400


def test_marcar_sem_conserto_ok(client_lab, os_no_lab):
    r = client_lab.post(f"/ordens/{os_no_lab}/desfecho-lab",
                        json={"desfecho": "sem_conserto", "obs": "carcaca trincada"})
    assert r.status_code == 200
    assert r.json()["desfecho_lab"] == "sem_conserto"


def test_marcar_concluido_sem_certificado_falha(client_lab, os_no_lab):
    r = client_lab.post(f"/ordens/{os_no_lab}/desfecho-lab",
                        json={"desfecho": "concluido", "obs": None})
    assert r.status_code == 409


def test_marcar_concluido_ok(client_lab, os_no_lab, db_session):
    from app.models import OSCertificado
    db_session.add(OSCertificado(os=os_no_lab, tipo="C"))
    db_session.commit()
    r = client_lab.post(f"/ordens/{os_no_lab}/desfecho-lab",
                        json={"desfecho": "concluido", "obs": None})
    assert r.status_code == 200
    assert r.json()["desfecho_lab"] == "concluido"
    assert r.json()["desfecho_lab_obs"] is None


def test_vincular_ordem_de_outro_cliente_falha(client_exp, caixa_com_os_cliente_a, os_cliente_b):
    r = client_exp.post(f"/caixas/{caixa_com_os_cliente_a}/ordens",
                        json={"ordem_id": os_cliente_b})
    assert r.status_code == 409
    assert "cliente" in r.json()["detail"].lower()


def test_abrir_os_com_caixa_de_outro_cliente_falha(client_exp, caixa_com_os_cliente_a, os_base):
    r = client_exp.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"],
        "tipo_servico": "C",
        "caixa": caixa_com_os_cliente_a,
    })
    assert r.status_code == 409
    assert "cliente" in r.json()["detail"].lower()


def test_avancar_caixa_recebido_para_lab(client_exp, caixa_recebido):
    r = client_exp.post(f"/caixas/{caixa_recebido}/avancar", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["fase"] == 5
    assert all(o["fase"] == 5 for o in body["ordens"])  # fan-out


def test_avancar_caixa_lab_travado_com_pendente(client_lab, caixa_lab_um_pendente):
    r = client_lab.post(f"/caixas/{caixa_lab_um_pendente}/avancar", json={})
    assert r.status_code == 409
    assert "faltam" in r.json()["detail"].lower()


def test_avancar_caixa_lab_libera_com_todos_terminais(client_lab, caixa_lab_todos_terminais):
    r = client_lab.post(f"/caixas/{caixa_lab_todos_terminais}/avancar", json={})
    assert r.status_code == 200
    assert r.json()["fase"] == 6


def test_avancar_caixa_finalizar_exige_cod_retorno(client_exp, caixa_preparando):
    r = client_exp.post(f"/caixas/{caixa_preparando}/avancar", json={})
    assert r.status_code == 422


def test_cancelar_caixa_cancela_todas(client_exp, caixa_recebido):
    r = client_exp.post(f"/caixas/{caixa_recebido}/cancelar", json={"motivo": "cliente desistiu"})
    assert r.status_code == 200
    assert all(o["fase"] == 9 for o in r.json()["ordens"])


def test_avancar_lab_espelha_calibracao_no_equipamento_cliente(client_lab, caixa_lab_com_calibracao, db_session):
    """Ao sair do laboratorio (5->6), a OS 'concluido' espelha os resultados de
    calibracao no EquipamentoCliente vinculado (`espelhar_calibracao` em
    `ordens_acoes.py`); a OS 'sem_conserto' NAO e espelhada — seu EC fica intocado."""
    from datetime import date
    from app.models import EquipamentoCliente

    cx_id = caixa_lab_com_calibracao["caixa"]
    r = client_lab.post(f"/caixas/{cx_id}/avancar", json={})
    assert r.status_code == 200
    assert r.json()["fase"] == 6

    ec_ok = db_session.get(EquipamentoCliente, caixa_lab_com_calibracao["ec_ok"])
    assert ec_ok.calib_cert == "C-1"
    assert ec_ok.calib_situacao == "Aprovado"
    assert ec_ok.calib_temp == "25"
    assert ec_ok.calib_pressao == "1013"
    assert ec_ok.calib_teste1 == "0.10"
    assert ec_ok.calib_teste2 == "0.11"
    assert ec_ok.calib_teste3 == "0.12"
    assert ec_ok.calib_teste_media == "0.11"
    assert ec_ok.ult_calibragem == date(2026, 7, 1)
    assert ec_ok.prox_calibragem == date(2027, 1, 1)

    ec_sc = db_session.get(EquipamentoCliente, caixa_lab_com_calibracao["ec_sc"])
    assert ec_sc.calib_cert is None
    assert ec_sc.calib_situacao is None
    assert ec_sc.ult_calibragem is None
    assert ec_sc.prox_calibragem is None


def test_avancar_posvendas_marca_aceite_em_todas_as_os(client_com, caixa_posvendas, db_session):
    """Ao sair de Pos-Vendas (6->10), toda OS ativa da caixa recebe `aceite=True`
    e `data_aceite` preenchida (fan-out do side-effect por OS)."""
    from app.models import Ordem

    r = client_com.post(f"/caixas/{caixa_posvendas}/avancar", json={})
    assert r.status_code == 200
    assert r.json()["fase"] == 10

    ordens = db_session.query(Ordem).filter(Ordem.caixa == caixa_posvendas).all()
    assert len(ordens) == 2
    for o in ordens:
        assert o.aceite is True
        assert o.data_aceite is not None


def test_avancar_financeiro_sem_nota_fiscal_falha(client_fin, caixa_financeiro):
    """O gate de NF barra o avanco Financeiro->Preparando (10->7) quando alguma OS
    ativa da caixa ainda nao tem `nota_fiscal` anexada."""
    r = client_fin.post(f"/caixas/{caixa_financeiro}/avancar", json={})
    assert r.status_code == 409
    assert "nota fiscal" in r.json()["detail"].lower()


def test_avancar_financeiro_com_nota_fiscal_marca_pago(client_fin, caixa_financeiro_com_nf, db_session):
    """Com a NF ja anexada em todas as OS ativas, o avanco (10->7) marca `pago=True`
    e `data_pagamento` em cada uma."""
    from app.models import Ordem

    r = client_fin.post(f"/caixas/{caixa_financeiro_com_nf}/avancar", json={})
    assert r.status_code == 200
    assert r.json()["fase"] == 7

    ordens = db_session.query(Ordem).filter(Ordem.caixa == caixa_financeiro_com_nf).all()
    assert len(ordens) == 2
    for o in ordens:
        assert o.pago is True
        assert o.data_pagamento is not None


def test_avancar_preparando_finaliza_com_cod_retorno(client_exp, caixa_preparando, db_session):
    """A finalizacao (7->8) grava `cod_retorno`, `data_retorno` e `situacao='F'`
    em toda OS ativa, alem de mover a fase da caixa e das OS para 8."""
    from app.models import Ordem

    r = client_exp.post(f"/caixas/{caixa_preparando}/avancar", json={"cod_retorno": "BR123"})
    assert r.status_code == 200
    assert r.json()["fase"] == 8

    ordens = db_session.query(Ordem).filter(Ordem.caixa == caixa_preparando).all()
    assert len(ordens) == 1
    o = ordens[0]
    assert o.situacao == "F"
    assert o.cod_retorno == "BR123"
    assert o.data_retorno is not None
    assert o.fase == 8


def _spy_agendamentos(monkeypatch):
    """Espiona os dois agendamentos externos chamados por `avancar_caixa`, sem
    depender de settings/integracao real nem de payload real — mesmo espirito do
    `_spy_gatilho` do (deletado) test_growthhs_gatilho_os.py, adaptado pra caixa."""
    import app.api.caixas as caixas_mod
    chamadas_taskhs = []
    chamadas_growthhs = []
    monkeypatch.setattr(
        caixas_mod, "agendar_espelhamento_caixa",
        lambda db, bt, cx, **kw: chamadas_taskhs.append(cx.id),
    )
    monkeypatch.setattr(
        caixas_mod, "agendar_card_caixa",
        lambda db, bt, cx: chamadas_growthhs.append(cx.id),
    )
    return chamadas_taskhs, chamadas_growthhs


def test_avancar_lab_agenda_taskhs_e_growthhs_uma_vez(client_lab, caixa_lab_todos_terminais, monkeypatch):
    """Sair do laboratorio (5->6) agenda os DOIS espelhamentos externos: o card da
    caixa no TaskHS (`agendar_espelhamento_caixa`, chamado em todo avanco) e o card
    de servicos liberados no GrowthHS (`agendar_card_caixa`, so' na saida do lab —
    gate `origem == wf.FASE_LABORATORIO` em `avancar_caixa`)."""
    chamadas_taskhs, chamadas_growthhs = _spy_agendamentos(monkeypatch)
    r = client_lab.post(f"/caixas/{caixa_lab_todos_terminais}/avancar", json={})
    assert r.status_code == 200
    assert r.json()["fase"] == 6
    assert chamadas_taskhs == [caixa_lab_todos_terminais]
    assert chamadas_growthhs == [caixa_lab_todos_terminais]


def test_avancar_fora_do_lab_nao_agenda_growthhs(client_exp, caixa_recebido, monkeypatch):
    """Uma transicao que NAO sai do laboratorio (4->5) agenda o espelhamento do
    TaskHS normalmente, mas NAO deve agendar o card do GrowthHS."""
    chamadas_taskhs, chamadas_growthhs = _spy_agendamentos(monkeypatch)
    r = client_exp.post(f"/caixas/{caixa_recebido}/avancar", json={})
    assert r.status_code == 200
    assert r.json()["fase"] == 5
    assert chamadas_taskhs == [caixa_recebido]
    assert chamadas_growthhs == []


def test_nf_caixa_replica_em_todas(client_fin, caixa_financeiro, upload_tmp):
    arquivo = ("nf.pdf", b"%PDF-1.4 fake", "application/pdf")
    r = client_fin.post(f"/caixas/{caixa_financeiro}/nota-fiscal",
                        data={"numero": "12345"}, files={"arquivo": arquivo})
    assert r.status_code == 200
    ordens = r.json()["ordens"]
    assert len(ordens) == 2
    baixadas = 0
    for o in ordens:
        det = client_fin.get(f"/ordens/{o['id']}").json()
        assert det["nota_fiscal_numero"] == "12345"
        resp_download = client_fin.get(f"/ordens/{o['id']}/nota-fiscal")
        if resp_download.status_code == 200:
            baixadas += 1
    # prova que a NF foi fisicamente replicada no subdir de cada OS, nao so o numero no banco
    assert baixadas == 2


def test_quadro_caixas_agrupa_por_fase(client_lab, caixa_lab_um_pendente):
    r = client_lab.get("/caixas/quadro")
    cols = {c["fase"]: c for c in r.json()}
    assert 5 in cols
    cx = cols[5]["caixas"][0]
    assert cx["total_os"] >= 1 and cx["pendentes"] >= 1
