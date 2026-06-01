from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, UsuarioCliente
from app.core.security import (
    verificar_senha,
    criar_access_token,
    criar_refresh_token,
    decodificar_token,
)
from app.schemas.auth import LoginRequest, Token, RefreshRequest, UsuarioOut
from app.api.deps import get_current_usuario
from jose import JWTError

router = APIRouter(prefix="/auth", tags=["auth"])


def _autenticar(registro, senha: str):
    if registro is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")
    if registro.precisa_redefinir_senha:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Senha precisa ser redefinida")
    if not verificar_senha(senha, registro.senha):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")


@router.post("/login", response_model=Token)
def login(dados: LoginRequest, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.login == dados.login).first()
    _autenticar(usuario, dados.senha)
    return Token(
        access_token=criar_access_token(sub=str(usuario.id), tipo="usuario"),
        refresh_token=criar_refresh_token(sub=str(usuario.id), tipo="usuario"),
    )


@router.post("/login-portal", response_model=Token)
def login_portal(dados: LoginRequest, db: Session = Depends(get_db)):
    cli = db.query(UsuarioCliente).filter(UsuarioCliente.login == dados.login).first()
    _autenticar(cli, dados.senha)
    return Token(
        access_token=criar_access_token(sub=str(cli.id), tipo="cliente"),
        refresh_token=criar_refresh_token(sub=str(cli.id), tipo="cliente"),
    )


@router.get("/me", response_model=UsuarioOut)
def me(usuario: Usuario = Depends(get_current_usuario)):
    return usuario


@router.post("/refresh", response_model=Token)
def refresh(dados: RefreshRequest):
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
    return Token(
        access_token=criar_access_token(sub=sub, tipo=tipo),
        refresh_token=criar_refresh_token(sub=sub, tipo=tipo),
    )
