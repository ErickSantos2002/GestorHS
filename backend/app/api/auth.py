import logging
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session
from jose import JWTError

from app.models.database import get_db
from app.models import Usuario, UsuarioCliente, Cliente
from app.core import emails, sso_tickets
from app.core.config import settings
from app.core.security import (
    hash_senha,
    verificar_senha,
    criar_access_token,
    criar_refresh_token,
    decodificar_token,
)
from app.integrations import microsoft_client
from app.schemas.auth import LoginRequest, PortalLoginRequest, Token, RefreshRequest, UsuarioOut, TrocarSenhaIn, LoginOut, DefinirSenhaIn, DefinirSenhaPortalIn, SsoExchangeIn
from app.api.deps import get_current_usuario

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# Hash fixo de descarte para achatar o timing quando o login não existe (anti-enumeração).
_DUMMY_HASH = hash_senha("timing-dummy-gestorhs")


def _verificar_credenciais(registro, senha: str) -> None:
    """401 se inexistente (com timing achatado) ou senha incorreta. Não bloqueia por precisa_redefinir."""
    if registro is None:
        verificar_senha(senha, _DUMMY_HASH)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")
    if not verificar_senha(senha, registro.senha):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")


@router.post("/login", response_model=LoginOut)
def login(dados: LoginRequest, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == emails.normalizar(dados.email)).first()
    _verificar_credenciais(usuario, dados.senha)
    if not usuario.ativo:
        raise HTTPException(status_code=403, detail="Usuário desativado. Fale com o administrador.")
    if usuario.precisa_redefinir_senha:
        return LoginOut(precisa_redefinir=True)
    return LoginOut(
        access_token=criar_access_token(sub=str(usuario.id), tipo="usuario"),
        refresh_token=criar_refresh_token(sub=str(usuario.id), tipo="usuario"),
    )


@router.post("/login-portal", response_model=LoginOut)
def login_portal(dados: PortalLoginRequest, db: Session = Depends(get_db)):
    doc = "".join(c for c in dados.documento if c.isdigit())
    empresa = db.query(Cliente).filter(or_(Cliente.cgc == doc, Cliente.cpf == doc)).first() if doc else None
    if empresa is None:
        _verificar_credenciais(None, dados.senha)
    cli = (
        db.query(UsuarioCliente)
        .filter(UsuarioCliente.cliente == empresa.id, UsuarioCliente.login == dados.login)
        .first()
    )
    _verificar_credenciais(cli, dados.senha)
    if cli.precisa_redefinir_senha:
        return LoginOut(precisa_redefinir=True)
    return LoginOut(
        access_token=criar_access_token(sub=str(cli.id), tipo="cliente", cliente=cli.cliente),
        refresh_token=criar_refresh_token(sub=str(cli.id), tipo="cliente", cliente=cli.cliente),
    )


@router.get("/me", response_model=UsuarioOut)
def me(usuario: Usuario = Depends(get_current_usuario)):
    return usuario


@router.post("/refresh", response_model=Token)
def refresh(dados: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = decodificar_token(dados.refresh_token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh inválido")
    if payload.get("token_use") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh inválido")
    sub = payload.get("sub")
    tipo = payload.get("tipo")
    if sub is None or tipo is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh inválido")
    try:
        sub_id = int(sub)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh inválido")

    # Revalida contra o banco: nega se o usuário sumiu ou precisa redefinir a senha.
    cliente_claim = None
    if tipo == "usuario":
        registro = db.query(Usuario).filter(Usuario.id == sub_id).first()
    elif tipo == "cliente":
        registro = db.query(UsuarioCliente).filter(UsuarioCliente.id == sub_id).first()
        cliente_claim = registro.cliente if registro is not None else None
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh inválido")

    # precisa_redefinir_senha so barra quem usou senha pra entrar: quem entrou
    # por SSO (via="sso") nao tem senha propria pra redefinir.
    via = payload.get("via")
    if registro is None or (registro.precisa_redefinir_senha and via != "sso"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh inválido")
    if tipo == "usuario" and not registro.ativo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh inválido")

    return Token(
        access_token=criar_access_token(sub=sub, tipo=tipo, cliente=cliente_claim, via=via),
        refresh_token=criar_refresh_token(sub=sub, tipo=tipo, cliente=cliente_claim, via=via),
    )


@router.post("/trocar-senha", status_code=status.HTTP_204_NO_CONTENT)
def trocar_senha(
    dados: TrocarSenhaIn,
    usuario: Usuario = Depends(get_current_usuario),
    db: Session = Depends(get_db),
):
    if usuario.precisa_redefinir_senha:
        raise HTTPException(status_code=403, detail="Senha precisa ser redefinida pelo administrador")
    if not verificar_senha(dados.senha_atual, usuario.senha):
        raise HTTPException(status_code=400, detail="senha atual incorreta")
    usuario.senha = hash_senha(dados.nova_senha)
    db.commit()


@router.post("/definir-senha", response_model=Token)
def definir_senha(dados: DefinirSenhaIn, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == emails.normalizar(dados.email)).first()
    _verificar_credenciais(usuario, dados.senha_atual)
    if not usuario.precisa_redefinir_senha:
        raise HTTPException(status_code=400, detail="conta não requer redefinição")
    usuario.senha = hash_senha(dados.nova_senha)
    usuario.precisa_redefinir_senha = False
    db.commit()
    return Token(
        access_token=criar_access_token(sub=str(usuario.id), tipo="usuario"),
        refresh_token=criar_refresh_token(sub=str(usuario.id), tipo="usuario"),
    )


@router.post("/definir-senha-portal", response_model=Token)
def definir_senha_portal(dados: DefinirSenhaPortalIn, db: Session = Depends(get_db)):
    doc = "".join(c for c in dados.documento if c.isdigit())
    empresa = db.query(Cliente).filter(or_(Cliente.cgc == doc, Cliente.cpf == doc)).first() if doc else None
    if empresa is None:
        _verificar_credenciais(None, dados.senha_atual)
    cli = (
        db.query(UsuarioCliente)
        .filter(UsuarioCliente.cliente == empresa.id, UsuarioCliente.login == dados.login)
        .first()
    )
    _verificar_credenciais(cli, dados.senha_atual)
    if not cli.precisa_redefinir_senha:
        raise HTTPException(status_code=400, detail="conta não requer redefinição")
    cli.senha = hash_senha(dados.nova_senha)
    cli.precisa_redefinir_senha = False
    db.commit()
    return Token(
        access_token=criar_access_token(sub=str(cli.id), tipo="cliente", cliente=cli.cliente),
        refresh_token=criar_refresh_token(sub=str(cli.id), tipo="cliente", cliente=cli.cliente),
    )


def _voltar_para_login(erro: str | None = None) -> RedirectResponse:
    """Volta para o /login, com ?erro= quando houver, e sempre apaga o cookie
    de state — o invariante fica estrutural em vez de repetido em cada
    chamador (era `resposta = ...` / `resposta.delete_cookie(...)` / `return
    resposta` em cada uma das 7 saídas de erro do callback)."""
    destino = f"{settings.FRONTEND_URL}/login"
    if erro:
        destino = f"{destino}?{urlencode({'erro': erro})}"
    resposta = RedirectResponse(destino, status_code=302)
    resposta.delete_cookie("sso_state")
    return resposta


def _ir_para_o_front(ticket: str) -> RedirectResponse:
    """Caminho feliz: manda o ticket para /auth/callback e apaga o cookie de
    state — irmão do `_voltar_para_login` para o mesmo invariante."""
    resposta = RedirectResponse(
        f"{settings.FRONTEND_URL}/auth/callback?{urlencode({'ticket': ticket})}", status_code=302
    )
    resposta.delete_cookie("sso_state")
    return resposta


@router.get("/microsoft")
def microsoft_autorizar():
    """Publico e de navegacao inteira: o botao no front e' uma ancora, nao um
    fetch — XHR nao segue redirect cross-origin."""
    if not settings.sso_ativo:
        raise HTTPException(status_code=503, detail="SSO Microsoft não configurado.")
    state = secrets.token_urlsafe(32)
    try:
        url_autorizacao = microsoft_client.url_de_autorizacao(state)
    except Exception:
        # Descoberta de autoridade do MSAL pode falhar (rede, Entra fora do
        # ar). Esta rota é navegação de página inteira — sem o try/except o
        # usuário veria o JSON de erro do FastAPI numa aba em branco, em vez
        # da mensagem no /login.
        logger.exception("Falha ao montar a URL de autorização do SSO Microsoft")
        return _voltar_para_login("falha_microsoft")
    resposta = RedirectResponse(url_autorizacao, status_code=302)
    resposta.set_cookie(
        "sso_state",
        state,
        max_age=600,
        httponly=True,
        samesite="lax",
        # O cookie mora no domínio da API, não no do front — é pelo esquema
        # do MS_REDIRECT_URI (onde o cookie é de fato setado) que "secure"
        # deve ser decidido, não pelo FRONTEND_URL.
        secure=settings.MS_REDIRECT_URI.startswith("https"),
    )
    return resposta


@router.get("/microsoft/callback")
def microsoft_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    """Para onde a Microsoft devolve o navegador. Termina sempre em redirect:
    ou para /auth/callback com o ticket, ou para /login com ?erro= (ou sem,
    quando quem cancelou foi o próprio usuário)."""
    if not settings.sso_ativo:
        raise HTTPException(status_code=503, detail="SSO Microsoft não configurado.")

    state_cookie = request.cookies.get("sso_state")
    if (
        not state
        or not state_cookie
        or not secrets.compare_digest(state.encode(), state_cookie.encode())
    ):
        # Sem state (ou nao batendo com o cookie): nao da pra confiar que o
        # code veio do navegador que a gente mesmo mandou pra Microsoft.
        return _voltar_para_login("falha_microsoft")

    if error == "access_denied":
        # O usuário cancelou o consentimento na tela da Microsoft — não é
        # falha do sistema, então volta sem ?erro= (retorno silencioso).
        return _voltar_para_login()

    if not code:
        return _voltar_para_login("falha_microsoft")

    try:
        token_ms = microsoft_client.trocar_code_por_token(code)
        email = emails.normalizar(microsoft_client.email_do_usuario(token_ms)) if token_ms else ""
    except Exception:
        # Rede, timeout, resposta estranha: o usuario ve a mensagem no login em
        # vez de um 500. O detalhe fica no log — e nunca inclui o token.
        logger.exception("Falha no callback do SSO Microsoft")
        return _voltar_para_login("falha_microsoft")

    if not email:
        return _voltar_para_login("falha_microsoft")

    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if usuario is None:
        # Sem provisionamento automatico: o cadastro continua na tela de
        # Usuarios, senao o tenant inteiro ganharia conta ao logar.
        return _voltar_para_login("usuario_nao_encontrado")
    if not usuario.ativo:
        return _voltar_para_login("usuario_inativo")

    # precisa_redefinir_senha NAO e' checado aqui de proposito: a flag forca a
    # troca de uma senha propria, e quem entra por SSO nao usou senha nenhuma.
    ticket = sso_tickets.emitir(
        criar_access_token(sub=str(usuario.id), tipo="usuario", via="sso"),
        criar_refresh_token(sub=str(usuario.id), tipo="usuario", via="sso"),
    )
    return _ir_para_o_front(ticket)


@router.post("/sso/exchange", response_model=Token)
def sso_exchange(dados: SsoExchangeIn):
    """Troca o ticket do redirect pelos tokens de verdade. Responde `Token` (e
    nao `LoginOut`): o SSO nunca devolve precisa_redefinir."""
    par = sso_tickets.resgatar(dados.ticket)
    if par is None:
        # 400 e nao 401 de proposito — ver o teste que fixa isso.
        raise HTTPException(status_code=400, detail="Link de acesso inválido ou expirado. Entre de novo.")
    access_token, refresh_token = par
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.get("/sso/status")
def sso_status():
    """Publico: o front pergunta antes de haver sessao, para decidir se mostra
    o botao 'Entrar com Microsoft'. Uma env so, em um lugar so — um
    VITE_SSO_ATIVO no build duplicaria a configuracao em duas pontas que podem
    discordar."""
    return {"ativo": settings.sso_ativo}
