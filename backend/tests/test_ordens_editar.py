def test_editar_exige_admin(client_lab, usuario_admin, os_no_lab):
    # client_lab e client_admin compartilham o mesmo TestClient (fixture `client` cacheada
    # por teste) — usar as duas fixtures ao mesmo tempo faria a segunda sobrescrever o
    # header Authorization da primeira. Por isso, aqui trocamos o header manualmente
    # no mesmo client em vez de misturar client_lab + client_admin.
    r = client_lab.put(f"/ordens/{os_no_lab}/editar", json={"tipo_servico": "C"})
    assert r.status_code == 403
    tok = client_lab.post("/auth/login", json={"email": "admin@hs.com", "senha": "senha123"}).json()
    r = client_lab.put(f"/ordens/{os_no_lab}/editar", json={"tipo_servico": "C"},
                        headers={"Authorization": f"Bearer {tok['access_token']}"})
    assert r.status_code == 200
    assert r.json()["tipo_servico"] == "C"


def test_editar_muda_tipo_recalcula_faltantes(client_admin, os_manutencao_iblow):
    # os_manutencao_iblow: OS tipo 'M' de um aparelho que só tem modelo de Calibração (C)
    r = client_admin.put(f"/ordens/{os_manutencao_iblow}/editar", json={"tipo_servico": "C"})
    assert r.status_code == 200
    assert r.json()["certificado_modelos_faltantes"] == []


def test_editar_condicao_invalida_400(client_admin, os_no_lab):
    r = client_admin.put(f"/ordens/{os_no_lab}/editar", json={"condicao_chegada": "xyz-invalida"})
    assert r.status_code == 400


def test_editar_nao_sobrescreve_campo_ausente(client_admin, os_com_obs):
    r = client_admin.put(f"/ordens/{os_com_obs}/editar", json={"pilhas": 2})
    assert r.status_code == 200
    body = r.json()
    assert body["pilhas"] == 2
    assert body["obs"] == "obs original"  # nao apagou o que nao veio (OrdemOut expoe "obs", nao "observacoes")
