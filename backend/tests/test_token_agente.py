"""Token de agente do HS.OS: o Guardi consulta o GestorHS como o dono (fase 1, so
leitura, allowlist em core/agente.py). A varredura das rotas fica em
test_funcao_consulta.py, junto da da funcao Consulta."""
import time

import pytest

from app.core.agente import ROTAS_AGENTE, TokenDeAgenteInvalido, eh_token_de_agente, validar_token_de_agente
from app.core.security import criar_access_token
from app.models import Usuario
from tests.conftest import _par_ed25519, emitir_token_agente

MSG_403 = "Ação não permitida para o agente"


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


# --- nucleo puro ------------------------------------------------------------

def test_valido_devolve_email_e_bot():
    priv, pem = _par_ed25519()
    assert validar_token_de_agente(emitir_token_agente(priv, "a@hs.com"), pem) == ("a@hs.com", "erick-bot")


def test_pem_com_barra_n_literal():
    # EasyPanel guarda a env numa linha so, com \n literal.
    priv, pem = _par_ed25519()
    assert validar_token_de_agente(emitir_token_agente(priv, "a@hs.com"), pem.replace("\n", "\\n"))[0] == "a@hs.com"


@pytest.mark.parametrize("sobrescreve", [
    {"aud": "taskhs"},
    {"iss": "outro"},
    {"exp": int(time.time()) - 10},
    {"exp": int(time.time()) + 3600},  # vida longa demais
    {"exp": None},
    {"act": None},
    {"act": {"sub": ""}},
])
def test_invalidos(sobrescreve):
    priv, pem = _par_ed25519()
    with pytest.raises(TokenDeAgenteInvalido):
        validar_token_de_agente(emitir_token_agente(priv, "a@hs.com", **sobrescreve), pem)


def test_chave_errada_e_chave_vazia():
    priv, _ = _par_ed25519()
    _, outra = _par_ed25519()
    tok = emitir_token_agente(priv, "a@hs.com")
    for chave in (outra, ""):
        with pytest.raises(TokenDeAgenteInvalido):
            validar_token_de_agente(tok, chave)


def test_hs256_com_iss_hsos_nao_passa():
    # Confusao de algoritmo: token HMAC assinado com a PEM publica como segredo.
    import jwt
    _, pem = _par_ed25519()
    tok = jwt.encode({"iss": "hsos", "aud": "gestorhs", "sub": "a@hs.com", "act": {"sub": "b"},
                      "exp": int(time.time()) + 60}, "segredo", algorithm="HS256")
    with pytest.raises(TokenDeAgenteInvalido):
        validar_token_de_agente(tok, pem)


def test_token_de_login_nao_e_de_agente():
    assert not eh_token_de_agente(criar_access_token("1", tipo="usuario"))
    assert not eh_token_de_agente("lixo")


# --- pela API ---------------------------------------------------------------

def test_entra_como_a_pessoa_com_a_funcao_dela(client_agente):
    resp = client_agente.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "admin@hs.com"
    assert resp.json()["funcao"] == "Administrador"
    assert client_agente.get("/clientes").status_code == 200


def test_funcao_do_dono_vale(client, usuario_consulta, fases_seed, agente):
    resp = client.get("/auth/me", headers=_h(agente("consulta@hs.com")))
    assert resp.status_code == 200
    assert resp.json()["email"] == "consulta@hs.com"
    assert resp.json()["funcao"] == "Consulta"


def test_allowlist_inteira_responde(client_agente):
    import re
    for rota in sorted(ROTAS_AGENTE):
        resp = client_agente.get(re.sub(r"\{[^}]+\}", "1", rota))
        assert resp.status_code not in (401, 403), f"{rota} -> {resp.status_code} {resp.text[:80]}"


@pytest.mark.parametrize("sobrescreve", [
    {"aud": "taskhs"},
    {"exp": int(time.time()) - 10},
    {"exp": int(time.time()) + 3600},
])
def test_token_ruim_401(client, usuario_admin, agente, sobrescreve):
    assert client.get("/clientes", headers=_h(agente("admin@hs.com", **sobrescreve))).status_code == 401


def test_chave_errada_401(client, usuario_admin, agente):
    priv, _ = _par_ed25519()
    assert client.get("/clientes", headers=_h(emitir_token_agente(priv, "admin@hs.com"))).status_code == 401


def test_sem_chave_configurada_401(client, usuario_admin, agente, monkeypatch):
    from app.core.config import settings
    tok = agente("admin@hs.com")
    monkeypatch.setattr(settings, "HSOS_AGENTE_CHAVE_PUBLICA", "")
    assert client.get("/clientes", headers=_h(tok)).status_code == 401
    # e o login de sempre segue funcionando
    login = client.post("/auth/login", json={"email": "admin@hs.com", "senha": "senha123"}).json()
    assert client.get("/clientes", headers=_h(login["access_token"])).status_code == 200


@pytest.mark.parametrize("email", ["ninguem@hs.com", "ADMIN@hs.com", " admin@hs.com"])
def test_email_inexistente_ou_nao_exato_401(client, usuario_admin, agente, email):
    assert client.get("/clientes", headers=_h(agente(email))).status_code == 401


def test_usuario_inativo_401(client, usuario_admin, agente, db_session):
    usuario_admin.ativo = False
    db_session.commit()
    assert client.get("/clientes", headers=_h(agente("admin@hs.com"))).status_code == 401


def test_post_403(client_agente):
    resp = client_agente.post("/clientes", json={"nome": "X"})
    assert resp.status_code == 403
    assert resp.json()["detail"] == MSG_403


@pytest.mark.parametrize("caminho", ["/empresas", "/usuarios", "/produtos", "/ordens/1/nota-fiscal"])
def test_get_fora_da_allowlist_403(client_agente, caminho):
    resp = client_agente.get(caminho)
    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"] == MSG_403


def test_auth_fora_do_me_403(client_agente):
    resp = client_agente.post("/auth/trocar-senha", json={"senha_atual": "senha123", "nova_senha": "outrasenha123"})
    assert resp.status_code == 403


def test_portal_nunca_aceita(client, cliente_portal, agente):
    # Mesmo com um Usuario interno do mesmo e-mail, o portal recusa.
    resp = client.get("/portal/me", headers=_h(agente("cliente1")))
    assert resp.status_code == 401


def test_guarda_o_bot_no_request(client_agente, monkeypatch):
    from fastapi import Depends, Request
    from app.api.deps import get_current_usuario
    from app.main import app
    import app.core.agente as mod

    @app.get("/_teste_agente_estado")
    def _rota(request: Request, _u: Usuario = Depends(get_current_usuario)):
        return {"bot": getattr(request.state, "agente", None)}

    try:
        assert client_agente.get("/_teste_agente_estado").status_code == 403  # fora da allowlist
        monkeypatch.setattr(mod, "ROTAS_AGENTE", mod.ROTAS_AGENTE | {"/_teste_agente_estado"})
        assert client_agente.get("/_teste_agente_estado").json() == {"bot": "erick-bot"}
    finally:
        app.router.routes.pop()
