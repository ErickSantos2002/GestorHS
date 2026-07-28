import logging
import secrets

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, UsuarioCliente
from app.core.config import settings
from app.core.security import decodificar_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

logger = logging.getLogger(__name__)

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
    if usuario is None or not usuario.ativo:
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


def require_growthhs_inbound(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    configurada = settings.GROWTHHS_INBOUND_API_KEY
    if not configurada:
        raise HTTPException(status_code=503, detail="integracao inbound do GrowthHS desligada")
    try:
        # compare_digest lanca TypeError se algum dos lados tiver caractere
        # nao-ASCII (Starlette decodifica headers como latin-1) — trata como
        # chave invalida em vez de deixar vazar como 500.
        valido = bool(x_api_key) and secrets.compare_digest(x_api_key, configurada)
    except TypeError:
        valido = False
    if not valido:
        logger.warning("GrowthHS inbound: X-API-Key invalida ou ausente")
        raise HTTPException(status_code=401, detail="api key invalida")


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


ADMIN = "Administrador"

# Quem pode CADASTRAR, ALTERAR e TRANSFERIR clientes e aparelhos da frota.
# Fonte unica: usada pelos routers de clientes e de equipamentos_cliente.
# Expedicao entra porque da entrada de modulos novos no estoque (cadastro de aparelhos).
# EXCLUIR continua so com Administrador — e a unica acao destrutiva de verdade.
GESTOR_CADASTRO = (ADMIN, "Laboratório", "Expedição")
