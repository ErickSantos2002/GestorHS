from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session
from jose import JWTError

from app.models.database import get_db
from app.models import Usuario, UsuarioCliente, Cliente
from app.core import emails
from app.core.config import settings
from app.core.security import (
    hash_senha,
    verificar_senha,
    criar_access_token,
    criar_refresh_token,
    decodificar_token,
)
from app.schemas.auth import LoginRequest, PortalLoginRequest, Token, RefreshRequest, UsuarioOut, TrocarSenhaIn, LoginOut, DefinirSenhaIn, DefinirSenhaPortalIn
from app.api.deps import get_current_usuario

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

    if registro is None or registro.precisa_redefinir_senha:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh inválido")
    if tipo == "usuario" and not registro.ativo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh inválido")

    return Token(
        access_token=criar_access_token(sub=sub, tipo=tipo, cliente=cliente_claim),
        refresh_token=criar_refresh_token(sub=sub, tipo=tipo, cliente=cliente_claim),
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


@router.get("/sso/status")
def sso_status():
    """Publico: o front pergunta antes de haver sessao, para decidir se mostra
    o botao 'Entrar com Microsoft'. Uma env so, em um lugar so — um
    VITE_SSO_ATIVO no build duplicaria a configuracao em duas pontas que podem
    discordar."""
    return {"ativo": settings.sso_ativo}
