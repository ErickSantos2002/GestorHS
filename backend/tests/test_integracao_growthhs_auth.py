"""Testes da dependency de auth inbound do GrowthHS (require_growthhs_inbound).

Monta um app FastAPI minimo, sem tocar no app principal (sem banco), com uma
unica rota protegida pela dependency — isola o teste da chave de config.
"""
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.deps import require_growthhs_inbound
from app.core.config import settings


@pytest.fixture()
def client():
    app = FastAPI()

    @app.get("/protegido", dependencies=[Depends(require_growthhs_inbound)])
    def _rota_protegida():
        return {"ok": True}

    return TestClient(app)


def test_chave_certa_retorna_200(client, monkeypatch):
    monkeypatch.setattr(settings, "GROWTHHS_INBOUND_API_KEY", "segredo-123")
    resp = client.get("/protegido", headers={"X-API-Key": "segredo-123"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_header_ausente_retorna_401(client, monkeypatch):
    monkeypatch.setattr(settings, "GROWTHHS_INBOUND_API_KEY", "segredo-123")
    resp = client.get("/protegido")
    assert resp.status_code == 401


def test_header_errado_retorna_401(client, monkeypatch):
    monkeypatch.setattr(settings, "GROWTHHS_INBOUND_API_KEY", "segredo-123")
    resp = client.get("/protegido", headers={"X-API-Key": "chave-errada"})
    assert resp.status_code == 401


def test_integracao_desligada_retorna_503(client, monkeypatch):
    monkeypatch.setattr(settings, "GROWTHHS_INBOUND_API_KEY", "")
    resp = client.get("/protegido", headers={"X-API-Key": "qualquer-coisa"})
    assert resp.status_code == 503


def test_header_nao_ascii_retorna_401_e_nao_500(client, monkeypatch):
    # Starlette decodifica headers de entrada como latin-1; secrets.compare_digest
    # lanca TypeError se o header decodificado carregar caracteres nao-ASCII (o
    # httpx do TestClient so aceita enviar isso como bytes latin-1 explicitos,
    # ja que um valor str puro seria forcado a ascii antes de sair). Precisa
    # falhar fechado com 401, nunca vazar como 500.
    monkeypatch.setattr(settings, "GROWTHHS_INBOUND_API_KEY", "segredo-123")
    resp = client.get(
        "/protegido",
        headers={"X-API-Key": "é-invalid".encode("latin-1")},
    )
    assert resp.status_code == 401
