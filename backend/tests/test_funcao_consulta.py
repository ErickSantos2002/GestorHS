"""Funcao Consulta: entra no /app e so le. A trava e' central (get_current_usuario),
nao rota a rota — o teste de varredura garante que rota de escrita nova nao escapa."""
import re

from fastapi.routing import APIRoute

from app.api.deps import get_current_usuario
from app.core.security import hash_senha
from app.models import Usuario

MSG = "Função Consulta é somente leitura"
ESCRITA = {"POST", "PUT", "PATCH", "DELETE"}
LIBERADAS = {"/auth/trocar-senha"}


def _depende_de_usuario(dependant) -> bool:
    for d in dependant.dependencies:
        if d.call is get_current_usuario or _depende_de_usuario(d):
            return True
    return False


def _api_routes(rotas):
    # FastAPI 0.139 embrulha cada include_router num _IncludedRouter; os routers do
    # main nao levam prefix no include, entao r.path ja e' o caminho final.
    for r in rotas:
        if isinstance(r, APIRoute):
            yield r
        elif hasattr(r, "original_router"):
            yield from _api_routes(r.original_router.routes)


def _rotas_de_escrita():
    from app.main import app
    for r in _api_routes(app.routes):
        if r.path in LIBERADAS:
            continue
        metodos = r.methods & ESCRITA
        if metodos and _depende_de_usuario(r.dependant):
            for m in sorted(metodos):
                yield m, re.sub(r"\{[^}]+\}", "1", r.path)


def test_toda_escrita_recusada(client_consulta):
    rotas = list(_rotas_de_escrita())
    assert len(rotas) > 50  # sanidade: a varredura achou as rotas de verdade
    falhas = []
    for metodo, caminho in rotas:
        resp = client_consulta.request(metodo, caminho, json={})
        if resp.status_code != 403 or resp.json().get("detail") != MSG:
            falhas.append(f"{metodo} {caminho} -> {resp.status_code} {resp.text[:80]}")
    assert falhas == []


def test_leituras_liberadas(client_consulta):
    for caminho in ["/clientes", "/empresas", "/equipamentos-cliente", "/equipamentos",
                    "/produtos", "/propostas", "/auth/me"]:
        assert client_consulta.get(caminho).status_code == 200, caminho


def test_trocar_senha_liberado(client_consulta):
    resp = client_consulta.post("/auth/trocar-senha",
                                json={"senha_atual": "senha123", "nova_senha": "outrasenha123"})
    assert resp.status_code == 204


def test_outras_funcoes_intactas(client_exp):
    resp = client_exp.post("/clientes", json={})
    assert resp.status_code != 403


def test_sem_funcao_nao_quebra(client, db_session):
    u = Usuario(nome="Sem", senha=hash_senha("senha123"), email="sem@hs.com",
                funcao_id=None, precisa_redefinir_senha=False)
    db_session.add(u); db_session.commit()
    tok = client.post("/auth/login", json={"email": "sem@hs.com", "senha": "senha123"}).json()
    resp = client.get("/clientes", headers={"Authorization": f"Bearer {tok['access_token']}"})
    assert resp.status_code == 200


# Escritas que NAO passam por get_current_usuario — logo, fora da trava da Consulta.
# Cada uma tem a sua propria porta (login/senha, token de cliente do portal, chave de
# API do inbound). Rota de escrita nova sem get_current_usuario quebra este teste de
# proposito: decida se ela devia estar travada antes de acrescentar aqui.
ESCRITA_SEM_USUARIO = {
    ("POST", "/auth/login"),
    ("POST", "/auth/login-portal"),
    ("POST", "/auth/refresh"),
    ("POST", "/auth/definir-senha"),
    ("POST", "/auth/definir-senha-portal"),
    ("POST", "/auth/sso/exchange"),
    ("POST", "/portal/solicitar-recalibracao"),
    ("POST", "/integracao/growthhs/caixas/{caixa_id}/ganho"),
    ("POST", "/integracao/taskhs/caixas/{caixa_id}/financeiro"),
}


def test_escritas_fora_da_trava_sao_so_as_conhecidas():
    from app.main import app
    achadas = {
        (m, r.path)
        for r in _api_routes(app.routes)
        for m in r.methods & ESCRITA
        if not _depende_de_usuario(r.dependant)
    }
    assert achadas == ESCRITA_SEM_USUARIO


# --- Token de agente do HS.OS (Guardi), fase 1 -----------------------------
# Mesma varredura, mais estrita: fora de GET na allowlist (core/agente.py), TODA rota
# que passa por get_current_usuario recusa o agente — escrita e leitura.
MSG_AGENTE = "Ação não permitida para o agente"


def _rotas_fora_da_allowlist_do_agente():
    from app.core.agente import agente_pode
    from app.main import app
    for r in _api_routes(app.routes):
        if not _depende_de_usuario(r.dependant):
            continue
        for m in sorted(r.methods - {"HEAD", "OPTIONS"}):
            if not agente_pode(m, r.path):
                yield m, re.sub(r"\{[^}]+\}", "1", r.path)


def test_agente_recusado_fora_da_allowlist(client_agente):
    rotas = list(_rotas_fora_da_allowlist_do_agente())
    assert len(rotas) > 100  # sanidade: escrita + leituras fora do catalogo
    falhas = []
    for metodo, caminho in rotas:
        resp = client_agente.request(metodo, caminho, json={})
        if resp.status_code != 403 or resp.json().get("detail") != MSG_AGENTE:
            falhas.append(f"{metodo} {caminho} -> {resp.status_code} {resp.text[:80]}")
    assert falhas == []


def test_allowlist_do_agente_so_tem_get_de_rota_que_existe():
    from app.core.agente import ROTAS_AGENTE
    from app.main import app
    gets = {r.path for r in _api_routes(app.routes) if "GET" in r.methods and _depende_de_usuario(r.dependant)}
    assert ROTAS_AGENTE - gets == set()
