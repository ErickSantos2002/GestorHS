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
    # fase 2c: o padrao da proposta e os catalogos que viram itens dela
    "/propostas/padrao",
    "/servicos",
    "/produtos",
    # proposta para empresa/filial: UF, nome e o cliente matriz (dono da frota)
    "/empresas/{empresa_id}",
    # Capacidade do Guardi (13/11/2026): o que ESTE login alcanca pelo agente
    "/agente/capacidades",
})
# Quem passa pela trava de fase (exige_funcao_da_fase): a funcao responsavel pela
# fase em que a caixa ESTA, mais o Administrador. A tabela de fases vive no banco.
POR_FASE = "por_fase"

# Fase 2a (nov/2026): as UNICAS escritas do agente, para a Expedicao pelo Guardi
# (sempre depois de a pessoa confirmar um cartao no HS.OS). Nelas a trava "so GET"
# cede e vale o require_funcao / exige_funcao_da_fase da rota, com a funcao do DONO.
# Spec: HS.OS/docs/superpowers/specs/2026-11-12-guardi-gestorhs-expedicao-design.md
#
# O valor e' quem a ROTA aceita (copia declarada do require_funcao dela), usado por
# GET /agente/capacidades. test_agente_capacidades.py percorre a tabela e confere,
# funcao a funcao, contra a rota de verdade — mudou o require_funcao, o teste cai.
FUNCOES_DAS_ESCRITAS: dict[tuple[str, str], tuple[str, ...] | str] = {
    ("POST", "/ordens"): ("Expedição", "Administrador"),
    # depende da fase da caixa: entra se a funcao avanca ALGUMA fase
    ("POST", "/caixas/{caixa_id}/avancar"): POR_FASE,
    ("POST", "/equipamentos-cliente"): ("Administrador", "Laboratório", "Expedição"),
    # Fase 2b (12/11/2026): o Laboratorio gera certificado pelo Guardi. O agente NAO
    # toca em cert_overrides (certificados_os.gerar). desfecho-lab segue FECHADO.
    # Spec: HS.OS/docs/superpowers/specs/2026-11-12-guardi-gestorhs-laboratorio-design.md
    ("POST", "/ordens/{ordem_id}/gerar-certificado"): ("Laboratório", "Administrador"),
    # Fase 2c (12/11/2026): Servicos e Financeiro criam e alteram proposta pelo Guardi.
    # O destinatario so VINCULA ao cadastro (nunca escreve nele) e nada agenda o Tiny.
    # Spec: HS.OS/docs/superpowers/specs/2026-11-12-guardi-gestorhs-propostas-design.md
    ("POST", "/propostas"): ("Comercial Pós-Vendas", "Administrador", "Financeiro"),
    ("PUT", "/propostas/{proposta_id}"): ("Comercial Pós-Vendas", "Administrador", "Financeiro"),
}
ESCRITAS_AGENTE = frozenset(FUNCOES_DAS_ESCRITAS)


def rotas_do_login(funcao: str | None, avanca_alguma_fase: bool) -> list[list[str]]:
    """Os pares [metodo, template] do allowlist que este login usa pelo agente.

    Os GETs valem para todo login (nenhum tem require_funcao). `avanca_alguma_fase`
    vem do chamador, que le a tabela de fases. -> lista ordenada, GETs primeiro."""
    rotas = [["GET", r] for r in sorted(ROTAS_AGENTE)]
    for (metodo, rota), quem in sorted(FUNCOES_DAS_ESCRITAS.items()):
        pode = avanca_alguma_fase if quem == POR_FASE else funcao in quem
        if pode:
            rotas.append([metodo, rota])
    return rotas


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
