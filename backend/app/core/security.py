from passlib.context import CryptContext

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
