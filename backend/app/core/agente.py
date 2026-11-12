"""Token de agente do HS.OS (JWT EdDSA): o Guardi consulta o GestorHS como o dono.

Funcao pura: sem config e sem banco. Usa PyJWT porque o python-jose (o do login
de sempre) NAO verifica EdDSA. Mesmo desenho do TaskHS (app/core/agente.py de la).
"""
import time

import jwt

# O HS.OS emite tokens de 5 min; a folga cobre diferenca de relogio.
VIDA_MAXIMA_SEGUNDOS = 600

# Fase 1 (nov/2026): o token de agente SO entra em GET destas rotas. Allowlist, nao
# lista negra: rota nova nasce fora, e PDFs, /exportar, notas fiscais, logs de
# integracao, usuarios e portal ficam fora sem precisar lembrar um por um. Rota nova
# so chega ao Guardi entrando nos DOIS catalogos: aqui e no HS.OS
# (docs/superpowers/specs/2026-11-11-guardi-gestorhs-design.md, repo HS.OS).
ROTAS_AGENTE = frozenset({
    "/auth/me",
    "/equipamentos-cliente",
    "/equipamentos-cliente/{item_id}",
    "/equipamentos-cliente/{item_id}/historico",
    "/equipamentos-cliente/{item_id}/ordens",
    "/equipamentos-cliente/{item_id}/certificados",
    "/equipamentos-cliente/resumo-por-modelo",
    "/equipamentos",
    "/clientes",
    "/clientes/{cliente_id}",
    "/ordens",
    "/ordens/{ordem_id}",
    "/ordens/{ordem_id}/certificados",
    "/ordens/{ordem_id}/certificado-campos",  # fase 2b
    "/fases",
    "/caixas",
    "/caixas/{caixa_id}",
    "/propostas",
    "/propostas/{proposta_id}",
    "/propostas/{proposta_id}/versoes",
})
# Fase 2a (nov/2026): as UNICAS escritas do agente, para a Expedicao pelo Guardi
# (sempre depois de a pessoa confirmar um cartao no HS.OS). Nelas a trava "so GET"
# cede e vale o require_funcao / exige_funcao_da_fase da rota, com a funcao do DONO.
# Spec: HS.OS/docs/superpowers/specs/2026-11-12-guardi-gestorhs-expedicao-design.md
ESCRITAS_AGENTE = frozenset({
    ("POST", "/ordens"),
    ("POST", "/caixas/{caixa_id}/avancar"),
    ("POST", "/equipamentos-cliente"),
    # Fase 2b (12/11/2026): o Laboratorio gera certificado pelo Guardi. O agente NAO
    # toca em cert_overrides (certificados_os.gerar). desfecho-lab segue FECHADO.
    # Spec: HS.OS/docs/superpowers/specs/2026-11-12-guardi-gestorhs-laboratorio-design.md
    ("POST", "/ordens/{ordem_id}/gerar-certificado"),
})


class TokenDeAgenteInvalido(Exception):
    pass


def eh_token_de_agente(token: str) -> bool:
    """Olha o payload SEM verificar: so decide o caminho (agente ou login normal)."""
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
    except Exception:
        return False
    return isinstance(payload, dict) and payload.get("iss") == "hsos"


def agente_pode(metodo: str, rota: str | None) -> bool:
    if metodo == "GET":
        return rota in ROTAS_AGENTE
    return (metodo, rota) in ESCRITAS_AGENTE


def validar_token_de_agente(token: str, chave_pem: str) -> tuple[str, str]:
    """-> (email, bot). Qualquer falha lanca TokenDeAgenteInvalido."""
    chave = (chave_pem or "").replace("\\n", "\n").strip()
    if not chave:
        raise TokenDeAgenteInvalido("chave publica nao configurada")
    try:
        payload = jwt.decode(
            token,
            chave,
            algorithms=["EdDSA"],
            audience="gestorhs",
            issuer="hsos",
            options={"require": ["exp", "sub", "iss", "aud"]},
        )
    except (jwt.PyJWTError, ValueError, TypeError) as exc:
        raise TokenDeAgenteInvalido(str(exc)) from exc
    if payload["exp"] - time.time() > VIDA_MAXIMA_SEGUNDOS:
        raise TokenDeAgenteInvalido("exp longe demais")
    email = payload.get("sub")
    act = payload.get("act")
    bot = act.get("sub") if isinstance(act, dict) else None
    if not isinstance(email, str) or not email or not isinstance(bot, str) or not bot:
        raise TokenDeAgenteInvalido("sub ou act.sub ausente")
    return email, bot
