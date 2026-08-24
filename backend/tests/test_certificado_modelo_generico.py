"""Modelo GENERICO (sem aparelho). Hoje so o tipo M usa esse caminho."""


def test_admin_grava_o_modelo_generico_de_manutencao(client_admin):
    r = client_admin.put("/certificados-modelo/generico?tipo=M",
                         json={"texto": "<p>[manutnumero]</p>", "descricao": "Relatório FORM-LAB-010"})
    assert r.status_code == 200
    assert r.json()["texto"] == "<p>[manutnumero]</p>"


def test_ler_o_modelo_generico(client_admin):
    client_admin.put("/certificados-modelo/generico?tipo=M", json={"texto": "<p>x</p>"})
    r = client_admin.get("/certificados-modelo/generico?tipo=M")
    assert r.status_code == 200
    assert r.json()["texto"] == "<p>x</p>"


def test_gravar_de_novo_atualiza_e_nao_duplica(client_admin, db_session):
    from app.models import CertificadoModelo
    client_admin.put("/certificados-modelo/generico?tipo=M", json={"texto": "<p>a</p>"})
    client_admin.put("/certificados-modelo/generico?tipo=M", json={"texto": "<p>b</p>"})
    db_session.expire_all()
    modelos = db_session.query(CertificadoModelo).filter(
        CertificadoModelo.equipamento.is_(None), CertificadoModelo.tipo == "M").all()
    assert len(modelos) == 1 and modelos[0].texto == "<p>b</p>"


def test_generico_de_calibracao_e_recusado(client_admin):
    """O registro legado tipo C existe e nao pode virar padrao de calibracao —
    a rota nem aceita criar generico de C."""
    r = client_admin.put("/certificados-modelo/generico?tipo=C", json={"texto": "<p>x</p>"})
    assert r.status_code == 422


def test_ler_generico_inexistente_404(client_admin):
    assert client_admin.get("/certificados-modelo/generico?tipo=M").status_code == 404
