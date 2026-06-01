from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)


def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    if not hash_armazenado:
        return False
    try:
        return pwd_context.verify(senha, hash_armazenado)
    except ValueError:
        # hash em formato inválido (ex.: valor legado) — nunca autentica
        return False


def _criar_token(sub: str, tipo: str, token_use: str, expira_em: timedelta) -> str:
    agora = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "tipo": tipo,            # "usuario" (equipe) ou "cliente" (portal)
        "token_use": token_use,  # "access" ou "refresh"
        "iat": agora,
        "exp": agora + expira_em,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def criar_access_token(sub: str, tipo: str) -> str:
    return _criar_token(sub, tipo, "access", timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))


def criar_refresh_token(sub: str, tipo: str) -> str:
    return _criar_token(sub, tipo, "refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))


def decodificar_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
