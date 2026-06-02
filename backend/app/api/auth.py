from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from jose import JWTError

from app.models.database import get_db
from app.models import Usuario, UsuarioCliente
from app.core.security import (
    hash_senha,
    verificar_senha,
    criar_access_token,
    criar_refresh_token,
    decodificar_token,
)
from app.schemas.auth import LoginRequest, PortalLoginRequest, Token, RefreshRequest, UsuarioOut, TrocarSenhaIn
from app.api.deps import get_current_usuario

router = APIRouter(prefix="/auth", tags=["auth"])

# Hash fixo de descarte para achatar o timing quando o login não existe (anti-enumeração).
_DUMMY_HASH = hash_senha("timing-dummy-gestorhs")


def _autenticar(registro, senha: str):
    if registro is None:
        verificar_senha(senha, _DUMMY_HASH)  # gasta o mesmo tempo de um verify real
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
def login_portal(dados: PortalLoginRequest, db: Session = Depends(get_db)):
    # Filtra pela CHAVE ÚNICA (cliente, login) — login não é único globalmente.
    cli = db.query(UsuarioCliente).filter(
        UsuarioCliente.cliente == dados.cliente,
        UsuarioCliente.login == dados.login,
    ).first()
    _autenticar(cli, dados.senha)
    return Token(
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
