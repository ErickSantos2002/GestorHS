def _headers(client, login, senha):
    tok = client.post("/auth/login", json={"login": login, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_listar_funcoes_admin(client, usuario_admin):
    r = client.get("/funcoes", headers=_headers(client, "admin", "senha123"))
    assert r.status_code == 200
    assert any(f["descricao"] == "Administrador" for f in r.json())


def test_funcoes_nega_nao_admin(client, usuario_comum):
    r = client.get("/funcoes", headers=_headers(client, "comum", "senha123"))
    assert r.status_code == 403


def test_listar_usuarios_admin(client, usuario_admin):
    r = client.get("/usuarios", headers=_headers(client, "admin", "senha123"))
    assert r.status_code == 200
    assert any(u["login"] == "admin" for u in r.json())


def test_usuarios_nega_nao_admin(client, usuario_comum):
    r = client.get("/usuarios", headers=_headers(client, "comum", "senha123"))
    assert r.status_code == 403


def test_criar_usuario(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    r = client.post("/usuarios", json={"login": "joao", "nome": "Joao", "senha": "segredo123"}, headers=h)
    assert r.status_code == 201
    assert r.json()["login"] == "joao"
    assert client.post("/auth/login", json={"login": "joao", "senha": "segredo123"}).status_code == 200


def test_criar_usuario_login_duplicado(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    r = client.post("/usuarios", json={"login": "admin", "senha": "segredo123"}, headers=h)
    assert r.status_code == 409


def test_criar_usuario_senha_curta(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    r = client.post("/usuarios", json={"login": "curto", "senha": "1234"}, headers=h)
    assert r.status_code == 422


def _criar(client, h, **kw):
    return client.post("/usuarios", json=kw, headers=h)


def test_obter_usuario_inexistente_404(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    r = client.get("/usuarios/99999", headers=h)
    assert r.status_code == 404


def test_atualizar_troca_funcao(client, usuario_admin, db_session):
    from app.models import Funcao
    lab = Funcao(descricao="Laboratório")
    db_session.add(lab)
    db_session.commit()
    h = _headers(client, "admin", "senha123")
    novo = _criar(client, h, login="maria", senha="segredo123").json()
    r = client.patch(f"/usuarios/{novo['id']}", json={"funcao_id": lab.id}, headers=h)
    assert r.status_code == 200
    assert r.json()["funcao"] == "Laboratório"


def test_atualizar_login_duplicado_409(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    novo = _criar(client, h, login="pedro", senha="segredo123").json()
    r = client.patch(f"/usuarios/{novo['id']}", json={"login": "admin"}, headers=h)
    assert r.status_code == 409


def test_patch_nega_rebaixar_ultimo_admin(client, usuario_admin, db_session):
    from app.models import Funcao
    lab = db_session.query(Funcao).filter(Funcao.descricao == "Laboratório").first()
    if lab is None:
        lab = Funcao(descricao="Laboratório")
        db_session.add(lab)
        db_session.commit()
    h = _headers(client, "admin", "senha123")
    # admin é o único Administrador; tentar tirar sua função admin -> 400
    r = client.patch(f"/usuarios/{usuario_admin.id}", json={"funcao_id": lab.id}, headers=h)
    assert r.status_code == 400


def test_excluir_a_si_mesmo_400(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    r = client.delete(f"/usuarios/{usuario_admin.id}", headers=h)
    assert r.status_code == 400


def test_excluir_usuario_comum_ok(client, usuario_admin):
    h = _headers(client, "admin", "senha123")
    novo = _criar(client, h, login="temp", senha="segredo123").json()
    r = client.delete(f"/usuarios/{novo['id']}", headers=h)
    assert r.status_code == 204
    assert client.get(f"/usuarios/{novo['id']}", headers=h).status_code == 404


def test_redefinir_senha_admin_deixa_temporaria(client, usuario_admin, db_session):
    from app.models import Usuario
    from app.core.security import hash_senha
    h = {"Authorization": f"Bearer {client.post('/auth/login', json={'login':'admin','senha':'senha123'}).json()['access_token']}"}
    alvo = Usuario(nome="Alvo", login="alvo", senha=hash_senha("antiga123"), precisa_redefinir_senha=False)
    db_session.add(alvo); db_session.commit(); db_session.refresh(alvo)
    r = client.post(f"/usuarios/{alvo.id}/redefinir-senha", json={"nova_senha": "temp12345"}, headers=h)
    assert r.status_code == 204
    db_session.refresh(alvo)
    assert alvo.precisa_redefinir_senha is True
    # login com a temporária sinaliza precisa_redefinir
    login = client.post("/auth/login", json={"login": "alvo", "senha": "temp12345"}).json()
    assert login["precisa_redefinir"] is True


def test_trocar_minha_senha_ok(client, usuario_comum):
    h = _headers(client, "comum", "senha123")
    r = client.post("/auth/trocar-senha", json={"senha_atual": "senha123", "nova_senha": "outraSenha9"}, headers=h)
    assert r.status_code == 204
    assert client.post("/auth/login", json={"login": "comum", "senha": "outraSenha9"}).status_code == 200


def test_trocar_minha_senha_atual_errada(client, usuario_comum):
    h = _headers(client, "comum", "senha123")
    r = client.post("/auth/trocar-senha", json={"senha_atual": "errada", "nova_senha": "outraSenha9"}, headers=h)
    assert r.status_code == 400


def test_trocar_senha_negada_se_precisa_redefinir(client, usuario_comum, db_session):
    from app.models import Usuario
    h = _headers(client, "comum", "senha123")
    # marca o usuário para redefinição forçada APÓS o login (token já em mãos)
    u = db_session.query(Usuario).filter(Usuario.login == "comum").first()
    u.precisa_redefinir_senha = True
    db_session.commit()
    r = client.post("/auth/trocar-senha", json={"senha_atual": "senha123", "nova_senha": "outraSenha9"}, headers=h)
    assert r.status_code == 403
