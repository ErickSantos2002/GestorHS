"""Normalização de e-mail (puro, sem I/O). O e-mail é a credencial do usuário interno."""


def normalizar(email: str | None) -> str:
    """Forma canônica para gravar e comparar: sem espaços nas pontas e em minúsculas."""
    return (email or "").strip().lower()
