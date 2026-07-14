"""Aparelho sem modelo de certificado cadastrado.

Bug real: gerar_certificados fazia `continue` quando nao havia modelo, devolvia lista
vazia e o endpoint respondia 200 OK — falha silenciosa. O usuario clicava em "Gerar
certificado" e nada acontecia, sem nenhum aviso. (12 de 44 aparelhos tinham modelo.)
"""


def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _os(db_session, os_base, tipo_servico="C", fase=5):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"],
              fase=fase, tipo_servico=tipo_servico, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    return o


def _modelo(db_session, os_base, tipo):
    from app.models import CertificadoModelo
    db_session.add(CertificadoModelo(equipamento=os_base["equipamento"], tipo=tipo, texto="<p>[serie]</p>"))
    db_session.commit()


def test_gerar_sem_modelo_nenhum_409(client, usuario_lab, fases_seed, os_base, db_session):
    """Aparelho sem NENHUM modelo: recusa com mensagem clara em vez de 200 silencioso."""
    o = _os(db_session, os_base)
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.post(f"/ordens/{o.id}/gerar-certificado", json={"calib_cert": "C-1"}, headers=h)
    assert r.status_code == 409
    detalhe = r.json()["detail"].lower()
    assert "modelo" in detalhe and "calibra" in detalhe   # diz QUAL modelo falta


def test_gerar_ambas_com_modelo_parcial_409_diz_qual_falta(client, usuario_lab, fases_seed, os_base, db_session):
    """Servico 'Ambas' pede C e M. So o C cadastrado -> recusa e aponta a Manutencao."""
    _modelo(db_session, os_base, "C")
    o = _os(db_session, os_base, tipo_servico="A")
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.post(f"/ordens/{o.id}/gerar-certificado", json={"calib_cert": "C-1"}, headers=h)
    assert r.status_code == 409
    detalhe = r.json()["detail"].lower()
    assert "manuten" in detalhe          # aponta o que falta
    assert "calibra" not in detalhe      # nao acusa o que ja existe


def test_gerar_com_todos_os_modelos_funciona(client, usuario_lab, fases_seed, os_base, db_session):
    """Regressao: com o modelo cadastrado, continua gerando normalmente."""
    _modelo(db_session, os_base, "C")
    o = _os(db_session, os_base)
    h = _headers(client, "lab@hs.com", "senha123")
    r = client.post(f"/ordens/{o.id}/gerar-certificado", json={"calib_cert": "C-1"}, headers=h)
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_obter_os_expoe_os_modelos_faltantes(client, usuario_lab, fases_seed, os_base, db_session):
    """A tela da OS precisa avisar ANTES de o usuario tentar gerar."""
    o = _os(db_session, os_base, tipo_servico="A")   # pede C e M, nenhum cadastrado
    h = _headers(client, "lab@hs.com", "senha123")
    body = client.get(f"/ordens/{o.id}", headers=h).json()
    assert body["certificado_modelos_faltantes"] == ["C", "M"]

    _modelo(db_session, os_base, "C")
    body = client.get(f"/ordens/{o.id}", headers=h).json()
    assert body["certificado_modelos_faltantes"] == ["M"]


def test_sem_faltantes_quando_tudo_cadastrado(client, usuario_lab, fases_seed, os_base, db_session):
    _modelo(db_session, os_base, "C")
    o = _os(db_session, os_base)
    h = _headers(client, "lab@hs.com", "senha123")
    body = client.get(f"/ordens/{o.id}", headers=h).json()
    assert body["certificado_modelos_faltantes"] == []


def test_avancar_tambem_devolve_os_modelos_faltantes(client, usuario_comum, fases_seed, os_base, db_session):
    """REGRESSAO: o campo so era preenchido no `obter`. Como `avancar` tambem devolve
    OrdemOut, o default [] do schema fazia o aviso sumir da tela (e o botao "Gerar"
    reaparecer) logo apos avancar a OS — levando o usuario direto ao 409."""
    o = _os(db_session, os_base, fase=4)          # aparelho sem nenhum modelo
    h = _headers(client, "comum@hs.com", "senha123")   # Expedicao: avanca 4->5
    r = client.post(f"/ordens/{o.id}/avancar", json={}, headers=h)
    assert r.status_code == 200
    assert r.json()["certificado_modelos_faltantes"] == ["C"]
