def test_login_sucesso_retorna_tokens(client, usuario_admin):
    r = client.post("/auth/login", json={"email": "admin@hs.com", "senha": "senha123"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["token_type"] == "bearer"
    assert corpo["access_token"]
    assert corpo["refresh_token"]


def test_login_com_email(client, usuario_admin):
    r = client.post("/auth/login", json={"email": "admin@hs.com", "senha": "senha123"})
    assert r.status_code == 200 and r.json()["access_token"]


def test_login_email_case_insensitive_e_com_espacos(client, usuario_admin):
    r = client.post("/auth/login", json={"email": "  Admin@HS.com ", "senha": "senha123"})
    assert r.status_code == 200 and r.json()["access_token"]


def test_login_email_inexistente_401(client, usuario_admin):
    assert client.post("/auth/login", json={"email": "naoexiste@hs.com", "senha": "senha123"}).status_code == 401


def test_login_senha_errada_401(client, usuario_admin):
    assert client.post("/auth/login", json={"email": "admin@hs.com", "senha": "errada99"}).status_code == 401


def test_login_legado_hash_vazio_401(client, db_session):
    from app.models import Usuario
    db_session.add(Usuario(nome="Velho", email="velho@hs.com", senha="", precisa_redefinir_senha=True))
    db_session.commit()
    r = client.post("/auth/login", json={"email": "velho@hs.com", "senha": "qualquer"})
    assert r.status_code == 401


def test_me_com_token(client, usuario_admin):
    tokens = client.post("/auth/login", json={"email": "admin@hs.com", "senha": "senha123"}).json()
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert r.status_code == 200
    assert r.json()["email"] == "admin@hs.com"


def test_me_sem_token_401(client):
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_refresh_gera_novo_access(client, usuario_admin):
    tokens = client.post("/auth/login", json={"email": "admin@hs.com", "senha": "senha123"}).json()
    r = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_me_sub_malformado_retorna_401(client, usuario_admin):
    from app.core.security import criar_access_token
    # token validamente assinado, mas com sub não-numérico
    token = criar_access_token(sub="nao-numerico", tipo="usuario")
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_refresh_sem_claims_retorna_401(client):
    from datetime import datetime, timedelta, timezone
    from jose import jwt
    from app.core.config import settings
    # refresh "incompleto": token_use correto mas sem sub/tipo
    agora = datetime.now(timezone.utc)
    token = jwt.encode(
        {"token_use": "refresh", "iat": agora, "exp": agora + timedelta(days=1)},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    r = client.post("/auth/refresh", json={"refresh_token": token})
    assert r.status_code == 401


def test_login_portal_sucesso(client, cliente_portal):
    r = client.post("/auth/login-portal", json={"documento": "11.222.333/0001-44", "login": "cliente1", "senha": "portal123"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["token_type"] == "bearer"
    assert corpo["access_token"] and corpo["refresh_token"]


def test_login_portal_documento_sem_pontuacao(client, cliente_portal):
    r = client.post("/auth/login-portal", json={"documento": "11222333000144", "login": "cliente1", "senha": "portal123"})
    assert r.status_code == 200


def test_login_portal_senha_errada_401(client, cliente_portal):
    r = client.post("/auth/login-portal", json={"documento": "11222333000144", "login": "cliente1", "senha": "errada"})
    assert r.status_code == 401


def test_login_portal_documento_inexistente_401(client, cliente_portal):
    r = client.post("/auth/login-portal", json={"documento": "00000000000000", "login": "cliente1", "senha": "portal123"})
    assert r.status_code == 401


def test_login_portal_login_errado_401(client, cliente_portal):
    r = client.post("/auth/login-portal", json={"documento": "11222333000144", "login": "naoexiste", "senha": "portal123"})
    assert r.status_code == 401


def test_token_portal_nao_acessa_me_de_usuario(client, cliente_portal):
    tokens = client.post("/auth/login-portal", json={"documento": "11222333000144", "login": "cliente1", "senha": "portal123"}).json()
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert r.status_code == 401


def test_login_portal_emite_claim_cliente_correto(client, cliente_portal):
    from app.core.security import decodificar_token
    tok = client.post("/auth/login-portal", json={"documento": "11222333000144", "login": "cliente1", "senha": "portal123"}).json()
    assert decodificar_token(tok["access_token"]).get("cliente") == cliente_portal.cliente


def test_refresh_apos_reset_e_negado(client, usuario_admin, db_session):
    from app.models import Usuario
    tokens = client.post("/auth/login", json={"email": "admin@hs.com", "senha": "senha123"}).json()
    # força a redefinição de senha no usuário
    u = db_session.query(Usuario).filter(Usuario.email == "admin@hs.com").first()
    u.precisa_redefinir_senha = True
    db_session.commit()
    r = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 401


def test_refresh_de_usuario_inexistente_e_negado(client):
    from app.core.security import criar_refresh_token
    # refresh validamente assinado para um id que não existe
    token = criar_refresh_token(sub="999999", tipo="usuario")
    r = client.post("/auth/refresh", json={"refresh_token": token})
    assert r.status_code == 401


def test_me_retorna_descricao_da_funcao(client, usuario_admin):
    tokens = client.post("/auth/login", json={"email": "admin@hs.com", "senha": "senha123"}).json()
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert r.status_code == 200
    assert r.json()["funcao"] == "Administrador"


def test_login_precisa_redefinir_sinaliza(client, db_session):
    from app.models import Usuario
    from app.core.security import hash_senha
    db_session.add(Usuario(nome="Temp", email="temp@hs.com", senha=hash_senha("provisoria1"), precisa_redefinir_senha=True))
    db_session.commit()
    r = client.post("/auth/login", json={"email": "temp@hs.com", "senha": "provisoria1"})
    assert r.status_code == 200
    body = r.json()
    assert body["precisa_redefinir"] is True
    assert body.get("access_token") in (None, "")


def test_login_normal_nao_pede_redefinir(client, usuario_admin):
    r = client.post("/auth/login", json={"email": "admin@hs.com", "senha": "senha123"})
    assert r.status_code == 200
    body = r.json()
    assert body.get("precisa_redefinir") in (False, None)
    assert body["access_token"]


def test_login_portal_precisa_redefinir(client, cliente_portal, db_session):
    from app.models import UsuarioCliente
    from app.core.security import hash_senha
    cli = db_session.query(UsuarioCliente).filter(UsuarioCliente.id == cliente_portal.id).first()
    cli.precisa_redefinir_senha = True
    cli.senha = hash_senha("provisoria1")
    db_session.commit()
    r = client.post("/auth/login-portal", json={"documento": "11222333000144", "login": "cliente1", "senha": "provisoria1"})
    assert r.status_code == 200 and r.json()["precisa_redefinir"] is True


def test_definir_senha_fluxo(client, db_session):
    from app.models import Usuario
    from app.core.security import hash_senha
    db_session.add(Usuario(nome="Temp", email="temp2@hs.com", senha=hash_senha("provisoria1"), precisa_redefinir_senha=True))
    db_session.commit()
    r = client.post("/auth/definir-senha", json={"email": "temp2@hs.com", "senha_atual": "provisoria1", "nova_senha": "novasenha123"})
    assert r.status_code == 200 and r.json()["access_token"]
    # login normal com a nova senha funciona e não pede redefinir
    r2 = client.post("/auth/login", json={"email": "temp2@hs.com", "senha": "novasenha123"})
    assert r2.status_code == 200 and r2.json()["access_token"] and not r2.json().get("precisa_redefinir")


def test_definir_senha_atual_errada_401(client, db_session):
    from app.models import Usuario
    from app.core.security import hash_senha
    db_session.add(Usuario(nome="Temp", email="temp3@hs.com", senha=hash_senha("provisoria1"), precisa_redefinir_senha=True))
    db_session.commit()
    r = client.post("/auth/definir-senha", json={"email": "temp3@hs.com", "senha_atual": "errada", "nova_senha": "novasenha123"})
    assert r.status_code == 401


def test_definir_senha_conta_sem_flag_400(client, usuario_admin):
    r = client.post("/auth/definir-senha", json={"email": "admin@hs.com", "senha_atual": "senha123", "nova_senha": "novasenha123"})
    assert r.status_code == 400


def test_definir_senha_portal_fluxo(client, cliente_portal, db_session):
    from app.models import UsuarioCliente
    from app.core.security import hash_senha
    cli = db_session.query(UsuarioCliente).filter(UsuarioCliente.id == cliente_portal.id).first()
    cli.precisa_redefinir_senha = True
    cli.senha = hash_senha("provisoria1")
    db_session.commit()
    r = client.post("/auth/definir-senha-portal", json={"documento": "11222333000144", "login": "cliente1", "senha_atual": "provisoria1", "nova_senha": "novasenha123"})
    assert r.status_code == 200 and r.json()["access_token"]
    r2 = client.post("/auth/login-portal", json={"documento": "11222333000144", "login": "cliente1", "senha": "novasenha123"})
    assert r2.status_code == 200 and r2.json()["access_token"] and not r2.json().get("precisa_redefinir")


def test_login_usuario_desativado_403(client, usuario_admin, usuario_comum, db_session):
    from app.models import Usuario
    alvo = db_session.query(Usuario).filter(Usuario.email == "comum@hs.com").first()
    alvo.ativo = False
    db_session.commit()
    r = client.post("/auth/login", json={"email": "comum@hs.com", "senha": "senha123"})
    assert r.status_code == 403
    assert "desativado" in r.json()["detail"].lower()


def test_token_de_usuario_desativado_401(client, usuario_admin, usuario_comum, db_session):
    from app.models import Usuario
    tok = client.post("/auth/login", json={"email": "comum@hs.com", "senha": "senha123"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    assert client.get("/auth/me", headers=h).status_code == 200
    alvo = db_session.query(Usuario).filter(Usuario.email == "comum@hs.com").first()
    alvo.ativo = False
    db_session.commit()
    assert client.get("/auth/me", headers=h).status_code == 401


def test_refresh_de_usuario_desativado_401(client, usuario_admin, usuario_comum, db_session):
    from app.models import Usuario
    tok = client.post("/auth/login", json={"email": "comum@hs.com", "senha": "senha123"}).json()
    alvo = db_session.query(Usuario).filter(Usuario.email == "comum@hs.com").first()
    alvo.ativo = False
    db_session.commit()
    r = client.post("/auth/refresh", json={"refresh_token": tok["refresh_token"]})
    assert r.status_code == 401
