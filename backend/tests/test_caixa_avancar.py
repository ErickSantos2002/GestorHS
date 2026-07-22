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
