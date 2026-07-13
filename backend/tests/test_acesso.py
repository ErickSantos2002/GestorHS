def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_listar_funcoes_admin(client, usuario_admin):
    r = client.get("/funcoes", headers=_headers(client, "admin@hs.com", "senha123"))
    assert r.status_code == 200
    assert any(f["descricao"] == "Administrador" for f in r.json())


def test_funcoes_nega_nao_admin(client, usuario_comum):
    r = client.get("/funcoes", headers=_headers(client, "comum@hs.com", "senha123"))
    assert r.status_code == 403


def test_listar_usuarios_admin(client, usuario_admin):
    r = client.get("/usuarios", headers=_headers(client, "admin@hs.com", "senha123"))
    assert r.status_code == 200
    assert any(u["email"] == "admin@hs.com" for u in r.json())


def test_usuarios_nega_nao_admin(client, usuario_comum):
    r = client.get("/usuarios", headers=_headers(client, "comum@hs.com", "senha123"))
    assert r.status_code == 403


def test_criar_usuario(client, usuario_admin):
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.post("/usuarios", json={"nome": "Joao", "email": "joao@hs.com", "senha": "segredo123"}, headers=h)
    assert r.status_code == 201
    assert r.json()["email"] == "joao@hs.com"
    assert client.post("/auth/login", json={"email": "joao@hs.com", "senha": "segredo123"}).status_code == 200


def test_criar_usuario_exige_email(client, usuario_admin):
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.post("/usuarios", json={"nome": "Joao", "senha": "segredo123"}, headers=h)
    assert r.status_code == 422


def test_criar_usuario_email_invalido_422(client, usuario_admin):
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.post("/usuarios", json={"nome": "Joao", "email": "nao-e-email", "senha": "segredo123"}, headers=h)
    assert r.status_code == 422


def test_criar_usuario_email_duplicado_409(client, usuario_admin):
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.post("/usuarios", json={"nome": "Outro", "email": "admin@hs.com", "senha": "segredo123"}, headers=h)
    assert r.status_code == 409


def test_criar_usuario_normaliza_email(client, usuario_admin):
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.post("/usuarios", json={"nome": "Joao", "email": "  Joao@HS.com ", "senha": "segredo123"}, headers=h)
    assert r.status_code == 201 and r.json()["email"] == "joao@hs.com"


def test_criar_usuario_senha_curta(client, usuario_admin):
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.post("/usuarios", json={"email": "curto@hs.com", "senha": "1234"}, headers=h)
    assert r.status_code == 422


def _criar(client, h, **kw):
    return client.post("/usuarios", json=kw, headers=h)


def test_obter_usuario_inexistente_404(client, usuario_admin):
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.get("/usuarios/99999", headers=h)
    assert r.status_code == 404


def test_atualizar_troca_funcao(client, usuario_admin, db_session):
    from app.models import Funcao
    lab = Funcao(descricao="Laboratório")
    db_session.add(lab)
    db_session.commit()
    h = _headers(client, "admin@hs.com", "senha123")
    novo = _criar(client, h, email="maria@hs.com", senha="segredo123").json()
    r = client.patch(f"/usuarios/{novo['id']}", json={"funcao_id": lab.id}, headers=h)
    assert r.status_code == 200
    assert r.json()["funcao"] == "Laboratório"


def test_atualizar_email_duplicado_409(client, usuario_admin):
    h = _headers(client, "admin@hs.com", "senha123")
    novo = _criar(client, h, email="pedro@hs.com", senha="segredo123").json()
    r = client.patch(f"/usuarios/{novo['id']}", json={"email": "admin@hs.com"}, headers=h)
    assert r.status_code == 409


def test_atualizar_email_null_422(client, usuario_admin, usuario_comum, db_session):
    from app.models import Usuario
    h = _headers(client, "admin@hs.com", "senha123")
    alvo = db_session.query(Usuario).filter(Usuario.email == "comum@hs.com").first()
    r = client.patch(f"/usuarios/{alvo.id}", json={"email": None}, headers=h)
    assert r.status_code == 422
    db_session.refresh(alvo)
    assert alvo.email == "comum@hs.com"   # inalterado


def test_patch_nega_rebaixar_ultimo_admin(client, usuario_admin, db_session):
    from app.models import Funcao
    lab = db_session.query(Funcao).filter(Funcao.descricao == "Laboratório").first()
    if lab is None:
        lab = Funcao(descricao="Laboratório")
        db_session.add(lab)
        db_session.commit()
    h = _headers(client, "admin@hs.com", "senha123")
    # admin é o único Administrador; tentar tirar sua função admin -> 400
    r = client.patch(f"/usuarios/{usuario_admin.id}", json={"funcao_id": lab.id}, headers=h)
    assert r.status_code == 400


def test_redefinir_senha_admin_deixa_temporaria(client, usuario_admin, db_session):
    from app.models import Usuario
    from app.core.security import hash_senha
    h = {"Authorization": f"Bearer {client.post('/auth/login', json={'email':'admin@hs.com','senha':'senha123'}).json()['access_token']}"}
    alvo = Usuario(nome="Alvo", email="alvo@hs.com", senha=hash_senha("antiga123"), precisa_redefinir_senha=False)
    db_session.add(alvo); db_session.commit(); db_session.refresh(alvo)
    r = client.post(f"/usuarios/{alvo.id}/redefinir-senha", json={"nova_senha": "temp12345"}, headers=h)
    assert r.status_code == 204
    db_session.refresh(alvo)
    assert alvo.precisa_redefinir_senha is True
    # login com a temporária sinaliza precisa_redefinir
    login = client.post("/auth/login", json={"email": "alvo@hs.com", "senha": "temp12345"}).json()
    assert login["precisa_redefinir"] is True


def test_trocar_minha_senha_ok(client, usuario_comum):
    h = _headers(client, "comum@hs.com", "senha123")
    r = client.post("/auth/trocar-senha", json={"senha_atual": "senha123", "nova_senha": "outraSenha9"}, headers=h)
    assert r.status_code == 204
    assert client.post("/auth/login", json={"email": "comum@hs.com", "senha": "outraSenha9"}).status_code == 200


def test_trocar_minha_senha_atual_errada(client, usuario_comum):
    h = _headers(client, "comum@hs.com", "senha123")
    r = client.post("/auth/trocar-senha", json={"senha_atual": "errada", "nova_senha": "outraSenha9"}, headers=h)
    assert r.status_code == 400


def test_trocar_senha_negada_se_precisa_redefinir(client, usuario_comum, db_session):
    from app.models import Usuario
    h = _headers(client, "comum@hs.com", "senha123")
    # marca o usuário para redefinição forçada APÓS o login (token já em mãos)
    u = db_session.query(Usuario).filter(Usuario.email == "comum@hs.com").first()
    u.precisa_redefinir_senha = True
    db_session.commit()
    r = client.post("/auth/trocar-senha", json={"senha_atual": "senha123", "nova_senha": "outraSenha9"}, headers=h)
    assert r.status_code == 403


def test_desativar_usuario(client, usuario_admin, usuario_comum, db_session):
    from app.models import Usuario
    h = _headers(client, "admin@hs.com", "senha123")
    alvo = db_session.query(Usuario).filter(Usuario.email == "comum@hs.com").first()
    r = client.post(f"/usuarios/{alvo.id}/desativar", headers=h)
    assert r.status_code == 204
    db_session.refresh(alvo)
    assert alvo.ativo is False


def test_reativar_usuario(client, usuario_admin, usuario_comum, db_session):
    from app.models import Usuario
    h = _headers(client, "admin@hs.com", "senha123")
    alvo = db_session.query(Usuario).filter(Usuario.email == "comum@hs.com").first()
    client.post(f"/usuarios/{alvo.id}/desativar", headers=h)
    r = client.post(f"/usuarios/{alvo.id}/reativar", headers=h)
    assert r.status_code == 204
    db_session.refresh(alvo)
    assert alvo.ativo is True


def test_nao_desativa_a_si_mesmo(client, usuario_admin):
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.post(f"/usuarios/{usuario_admin.id}/desativar", headers=h)
    assert r.status_code == 400


def test_admin_pode_desativar_outro_admin(client, usuario_admin, usuario_comum, db_session):
    # com 2 admins ativos, um pode desativar o outro (a guarda do "ultimo admin" nao dispara)
    from app.models import Usuario, Funcao
    admin_funcao = db_session.query(Funcao).filter(Funcao.descricao == "Administrador").first()
    outro = db_session.query(Usuario).filter(Usuario.email == "comum@hs.com").first()
    outro.funcao_id = admin_funcao.id
    db_session.commit()
    h = _headers(client, "comum@hs.com", "senha123")   # "comum" agora e admin
    r = client.post(f"/usuarios/{usuario_admin.id}/desativar", headers=h)
    assert r.status_code == 204
    db_session.refresh(usuario_admin)
    assert usuario_admin.ativo is False


def test_listar_oculta_inativos_por_padrao(client, usuario_admin, usuario_comum, db_session):
    from app.models import Usuario
    h = _headers(client, "admin@hs.com", "senha123")
    alvo = db_session.query(Usuario).filter(Usuario.email == "comum@hs.com").first()
    client.post(f"/usuarios/{alvo.id}/desativar", headers=h)
    ids = [u["id"] for u in client.get("/usuarios", headers=h).json()]
    assert alvo.id not in ids
    ids_todos = [u["id"] for u in client.get("/usuarios?incluir_inativos=true", headers=h).json()]
    assert alvo.id in ids_todos


def test_delete_usuario_nao_existe_mais(client, usuario_admin, usuario_comum, db_session):
    from app.models import Usuario
    h = _headers(client, "admin@hs.com", "senha123")
    alvo = db_session.query(Usuario).filter(Usuario.email == "comum@hs.com").first()
    r = client.delete(f"/usuarios/{alvo.id}", headers=h)
    assert r.status_code == 405   # método não permitido: a rota DELETE foi removida
