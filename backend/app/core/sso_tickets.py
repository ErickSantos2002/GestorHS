"""Tickets opacos de uso unico para o retorno do SSO Microsoft.

O callback nao pode devolver os tokens na URL: query string entra no historico
do navegador, no Referer da proxima requisicao e em qualquer log de proxy no
caminho — e o que vazaria aqui e' um refresh token de 7 dias. Entao o callback
guarda o par aqui e manda so o ticket, que o front troca num POST.

ASSUME PROCESSO UNICO. O estado e' um dict em memoria: com mais de um worker o
exchange cai num processo que nao emitiu o ticket e o login falha de forma
intermitente. Se o deploy ganhar --workers > 1, a correcao e' estado
compartilhado (Redis ou tabela com TTL). Reiniciar o backend descarta tickets
pendentes — quem estava no meio do redirect clica de novo.
"""
import secrets
import time

TTL_SEGUNDOS = 60

# ticket -> (access_token, refresh_token, expira_em)
_tickets: dict[str, tuple[str, str, float]] = {}


def _limpar_vencidos(agora: float) -> None:
    for chave in [k for k, (_, _, expira) in _tickets.items() if expira <= agora]:
        _tickets.pop(chave, None)


def emitir(access_token: str, refresh_token: str) -> str:
    """Guarda o par e devolve o ticket que vai na URL de retorno."""
    agora = time.monotonic()
    _limpar_vencidos(agora)
    ticket = secrets.token_urlsafe(32)
    _tickets[ticket] = (access_token, refresh_token, agora + TTL_SEGUNDOS)
    return ticket


def resgatar(ticket: str) -> tuple[str, str] | None:
    """Uso unico: o pop acontece antes da checagem de validade, entao um ticket
    vencido tambem sai do dict ao ser tentado."""
    registro = _tickets.pop(ticket, None)
    if registro is None:
        return None
    access_token, refresh_token, expira_em = registro
    if expira_em <= time.monotonic():
        return None
    return access_token, refresh_token
