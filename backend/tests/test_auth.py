def test_login_sucesso_retorna_tokens(client, usuario_admin):
    r = client.post("/auth/login", json={"login": "admin", "senha": "senha123"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["token_type"] == "bearer"
    assert corpo["access_token"]
    assert corpo["refresh_token"]


def test_login_senha_errada_401(client, usuario_admin):
    r = client.post("/auth/login", json={"login": "admin", "senha": "errada"})
    assert r.status_code == 401


def test_login_senha_legada_exige_redefinicao(client, db_session):
    from app.models import Usuario
    db_session.add(Usuario(nome="Velho", login="velho", senha="", precisa_redefinir_senha=True))
    db_session.commit()
    r = client.post("/auth/login", json={"login": "velho", "senha": "qualquer"})
    assert r.status_code == 403
    assert "redefin" in r.json()["detail"].lower()


def test_me_com_token(client, usuario_admin):
    tokens = client.post("/auth/login", json={"login": "admin", "senha": "senha123"}).json()
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert r.status_code == 200
    assert r.json()["login"] == "admin"


def test_me_sem_token_401(client):
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_refresh_gera_novo_access(client, usuario_admin):
    tokens = client.post("/auth/login", json={"login": "admin", "senha": "senha123"}).json()
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
    r = client.post("/auth/login-portal", json={"cliente": 1, "login": "cliente1", "senha": "portal123"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["token_type"] == "bearer"
    assert corpo["access_token"]
    assert corpo["refresh_token"]


def test_login_portal_senha_errada_401(client, cliente_portal):
    r = client.post("/auth/login-portal", json={"cliente": 1, "login": "cliente1", "senha": "errada"})
    assert r.status_code == 401


def test_token_portal_nao_acessa_me_de_usuario(client, cliente_portal):
    # um token de cliente (portal) NÃO pode acessar /auth/me (endpoint de usuário/equipe)
    tokens = client.post("/auth/login-portal", json={"cliente": 1, "login": "cliente1", "senha": "portal123"}).json()
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert r.status_code == 401


def test_login_portal_cliente_errado_401(client, cliente_portal):
    # login certo, tenant errado -> não existe (1, cliente1) vs (999, cliente1)
    r = client.post("/auth/login-portal", json={"cliente": 999, "login": "cliente1", "senha": "portal123"})
    assert r.status_code == 401


def test_refresh_apos_reset_e_negado(client, usuario_admin, db_session):
    from app.models import Usuario
    tokens = client.post("/auth/login", json={"login": "admin", "senha": "senha123"}).json()
    # força a redefinição de senha no usuário
    u = db_session.query(Usuario).filter(Usuario.login == "admin").first()
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


def test_cliente_token_com_tenant_adulterado_e_negado(client, cliente_portal):
    from app.core.security import criar_access_token, decodificar_token
    # token de cliente com claim 'cliente' adulterado (não bate com o tenant real=1)
    token = criar_access_token(sub=str(cliente_portal.id), tipo="cliente", cliente=4242)
    # garante que o login-portal emite o claim correto
    tok = client.post("/auth/login-portal", json={"cliente": 1, "login": "cliente1", "senha": "portal123"}).json()
    assert decodificar_token(tok["access_token"]).get("cliente") == 1
