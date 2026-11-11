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
