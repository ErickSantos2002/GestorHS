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
