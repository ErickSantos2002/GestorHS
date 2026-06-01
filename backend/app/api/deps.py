from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, UsuarioCliente
from app.core.security import decodificar_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

_cred_invalida = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciais inválidas",
    headers={"WWW-Authenticate": "Bearer"},
)


def _payload_valido(token: str, tipo_esperado: str) -> dict:
    try:
        dados = decodificar_token(token)
    except JWTError:
        raise _cred_invalida
    if dados.get("token_use") != "access" or dados.get("tipo") != tipo_esperado:
        raise _cred_invalida
    return dados


def get_current_usuario(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Usuario:
    dados = _payload_valido(token, "usuario")
    try:
        sub_id = int(dados["sub"])
    except (KeyError, ValueError, TypeError):
        raise _cred_invalida
    usuario = db.query(Usuario).filter(Usuario.id == sub_id).first()
    if usuario is None:
        raise _cred_invalida
    return usuario


def get_current_cliente(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> UsuarioCliente:
    dados = _payload_valido(token, "cliente")
    try:
        sub_id = int(dados["sub"])
    except (KeyError, ValueError, TypeError):
        raise _cred_invalida
    cli = db.query(UsuarioCliente).filter(UsuarioCliente.id == sub_id).first()
    if cli is None:
        raise _cred_invalida
    if dados.get("cliente") != cli.cliente:
        raise _cred_invalida
    return cli


def require_funcao(*descricoes: str):
    def _checagem(usuario: Usuario = Depends(get_current_usuario), db: Session = Depends(get_db)) -> Usuario:
        from app.models import Funcao
        if usuario.funcao_id is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem função atribuída")
        funcao = db.query(Funcao).filter(Funcao.id == usuario.funcao_id).first()
        if funcao is None or funcao.descricao not in descricoes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado para sua função")
        return usuario
    return _checagem
