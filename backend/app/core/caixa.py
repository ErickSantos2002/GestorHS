"""Lógica pura de composição de clientes de uma caixa (sem I/O)."""
from collections.abc import Iterable


def _distintos(clientes: Iterable[int | None]) -> set[int]:
    return {c for c in clientes if c is not None}


def contar_outros(clientes: Iterable[int | None]) -> int:
    """Quantos clientes além do principal exibido no card (= distintos - 1)."""
    return max(0, len(_distintos(clientes)) - 1)


def principal_valido(principal: int | None, clientes: Iterable[int | None]) -> int | None:
    """O principal só vale se ainda estiver entre os clientes da caixa; senão None (fallback)."""
    if principal is not None and principal in _distintos(clientes):
        return principal
    return None


def cliente_unico(clientes: Iterable[int | None]) -> int | None:
    """O único cliente distinto, se houver exatamente um; senão None."""
    d = _distintos(clientes)
    return next(iter(d)) if len(d) == 1 else None
