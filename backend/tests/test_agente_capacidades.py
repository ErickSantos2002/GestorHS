"""GET /agente/capacidades (13/11/2026): o que o Guardi alcanca com o login do dono.

A tabela core/agente.FUNCOES_DAS_ESCRITAS e' copia declarada do require_funcao de
cada rota. O teste de varredura prende a copia ao codigo: para cada funcao, cada par
do allowlist que a rota de capacidades devolve NAO recebe a recusa de funcao na rota
de verdade, e cada par que ela nao devolve recebe."""
import re

import pytest

from app.core import os_workflow as wf
from app.core.agente import ESCRITAS_AGENTE, FUNCOES_DAS_ESCRITAS, POR_FASE, ROTAS_AGENTE
from app.core.security import hash_senha
from app.models import Caixa, Funcao, Usuario

FUNCOES = ["Administrador", "Expedição", "Laboratório", "Comercial Pós-Vendas",
           "Financeiro", "Consulta", None]
RECUSAS = {"Acesso negado para sua função", "Acesso negado para sua função nesta fase",
           "Sem função atribuída", "Função Consulta é somente leitura"}
FASES_COM_SAIDA = sorted(set(wf.PROXIMA) | set(wf.PROXIMA_SO_MODULO))


def _email(funcao):
    return f"{re.sub(r'[^a-z]', '', (funcao or 'semfuncao').lower())}@cap.hs"


@pytest.fixture()
def usuarios(db_session, fases_seed):
    for nome in FUNCOES:
        fid = None
        if nome:
            f = db_session.query(Funcao).filter(Funcao.descricao == nome).first()
            if f is None:
                f = Funcao(descricao=nome); db_session.add(f); db_session.flush()
            fid = f.id
        db_session.add(Usuario(nome=nome or "Sem", senha=hash_senha("x"), email=_email(nome),
                               funcao_id=fid, precisa_redefinir_senha=False))
    db_session.commit()


@pytest.fixture()
def como(client, usuarios, agente):
    def _como(funcao):
        client.headers["Authorization"] = f"Bearer {agente(_email(funcao))}"
        return client
    return _como


def _recusada(r) -> bool:
    if r.status_code != 403:
        return False
    assert r.json()["detail"] in RECUSAS, r.text  # nenhum outro 403 (ex.: allowlist)
    return True


def _chamar(c, metodo, rota):
    url = re.sub(r"\{[^}]+\}", "999999", rota)
    return c.get(url) if metodo == "GET" else c.request(metodo, url, json={})


def _avanco_recusado(c, db):
    """Recusado so se TODAS as fases com saida recusam (caixa nova a cada fase)."""
    recusas = []
    for fase in FASES_COM_SAIDA:
        cx = Caixa(obs="cap", fase=fase); db.add(cx); db.commit()
        recusas.append(_recusada(c.post(f"/caixas/{cx.id}/avancar", json={})))
    return all(recusas)


@pytest.mark.parametrize("funcao", FUNCOES)
def test_capacidades_batem_com_as_rotas(como, db_session, funcao):
    c = como(funcao)
    r = c.get("/agente/capacidades")
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["papel"] == (funcao or "Sem função")
    devolvidas = {tuple(p) for p in corpo["rotas"]}
    todas = {("GET", g) for g in ROTAS_AGENTE} | set(ESCRITAS_AGENTE)
    assert devolvidas <= todas
    for metodo, rota in sorted(todas - {("GET", "/agente/capacidades")}):
        if (metodo, rota) == ("POST", "/caixas/{caixa_id}/avancar"):
            recusada = _avanco_recusado(c, db_session)
        else:
            recusada = _recusada(_chamar(c, metodo, rota))
        assert recusada == ((metodo, rota) not in devolvidas), (funcao, metodo, rota)


def test_exemplos(como):
    def rotas(f):
        return {tuple(p) for p in como(f).get("/agente/capacidades").json()["rotas"]}
    exp, lab, com, cons = rotas("Expedição"), rotas("Laboratório"), rotas("Comercial Pós-Vendas"), rotas("Consulta")
    assert ("POST", "/ordens") in exp and ("POST", "/ordens") not in lab
    assert ("POST", "/ordens/{ordem_id}/gerar-certificado") in lab
    assert ("POST", "/caixas/{caixa_id}/avancar") in com  # responsavel pela fase 6
    assert ("POST", "/propostas") in com and ("POST", "/propostas") not in exp
    assert all(m == "GET" for m, _ in cons) and ("GET", "/ordens") in cons
    assert ("GET", "/agente/capacidades") in cons


def test_tabela_cobre_as_escritas():
    assert set(FUNCOES_DAS_ESCRITAS) == set(ESCRITAS_AGENTE)
    assert all(v == POR_FASE or isinstance(v, tuple) for v in FUNCOES_DAS_ESCRITAS.values())


def test_login_normal_404(client_admin):
    assert client_admin.get("/agente/capacidades").status_code == 404


def test_sem_conta_401(client, fases_seed, agente):
    client.headers["Authorization"] = f"Bearer {agente('ninguem@hs.com')}"
    assert client.get("/agente/capacidades").status_code == 401
