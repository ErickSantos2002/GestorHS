import json

import httpx
import pytest

from app.core.config import settings
from app.integrations import tiny_client


class FakeResp:
    def __init__(self, corpo, status_code=200):
        self.status_code = status_code
        self._corpo = corpo
        self.text = json.dumps(corpo)
        self.headers = {"x-limit-api": "20"}

    def json(self):
        return self._corpo


@pytest.fixture()
def ativa(monkeypatch):
    monkeypatch.setattr(settings, "TINY_TOKEN", "tok-123")
    monkeypatch.setattr(settings, "TINY_BASE_URL", "https://api.tiny.test/api2")


@pytest.fixture(autouse=True)
def _sem_banco(monkeypatch):
    monkeypatch.setattr(tiny_client, "registrar_log_integracao", lambda **kw: None)


def _captura(monkeypatch, corpo):
    capturado = {}

    def fake_post(url, data=None, timeout=None):
        capturado["url"] = url
        capturado["data"] = data
        capturado["timeout"] = timeout
        return FakeResp(corpo)

    monkeypatch.setattr(httpx, "post", fake_post)
    return capturado


def test_integracao_ativa_depende_do_token(monkeypatch):
    monkeypatch.setattr(settings, "TINY_TOKEN", "")
    assert tiny_client.integracao_ativa() is False
    monkeypatch.setattr(settings, "TINY_TOKEN", "tok")
    assert tiny_client.integracao_ativa() is True


def test_desligado_nao_faz_chamada(monkeypatch):
    monkeypatch.setattr(settings, "TINY_TOKEN", "")
    chamou = []
    monkeypatch.setattr(httpx, "post", lambda *a, **k: chamou.append(1))
    r = tiny_client.incluir_contato({"nome": "X"})
    assert chamou == [] and not r.ok


def test_pesquisar_contato_encontrado(monkeypatch, ativa):
    cap = _captura(monkeypatch, {"retorno": {"status": "OK", "contatos": [
        {"contato": {"id": "565052083", "nome": "SUMA BRASIL"}}]}})
    r = tiny_client.pesquisar_contato("16565111002048")
    assert r.ok and r.id == 565052083
    assert cap["url"] == "https://api.tiny.test/api2/contatos.pesquisa.php"
    assert cap["data"]["token"] == "tok-123" and cap["data"]["formato"] == "json"
    assert cap["data"]["cpf_cnpj"] == "16565111002048"


def test_pesquisar_contato_nao_encontrado(monkeypatch, ativa):
    _captura(monkeypatch, {"retorno": {"status": "Erro", "codigo_erro": "20",
                                       "erros": [{"erro": "A consulta não retornou registros"}]}})
    r = tiny_client.pesquisar_contato("36312056000552")
    assert not r.ok and r.nao_encontrado


def test_incluir_contato_manda_o_json_no_campo_contato(monkeypatch, ativa):
    cap = _captura(monkeypatch, {"retorno": {"status": "OK", "registros": [
        {"registro": {"sequencia": "1", "status": "OK", "id": 610661344}}]}})
    r = tiny_client.incluir_contato({"nome": "Filial", "situacao": "A", "sequencia": 1})
    assert r.ok and r.id == 610661344
    assert cap["url"].endswith("/contato.incluir.php")
    enviado = json.loads(cap["data"]["contato"])
    assert enviado == {"contatos": [{"contato": {"nome": "Filial", "situacao": "A", "sequencia": 1}}]}


def test_alterar_contato_usa_o_endpoint_de_alteracao(monkeypatch, ativa):
    cap = _captura(monkeypatch, {"retorno": {"status": "OK", "registros": [
        {"registro": {"sequencia": "1", "status": "OK", "id": 610661344}}]}})
    r = tiny_client.alterar_contato({"id": 610661344, "nome": "Filial", "situacao": "A", "sequencia": 1})
    assert r.ok and cap["url"].endswith("/contato.alterar.php")


def test_obter_contato_devolve_o_contato_singular(monkeypatch, ativa):
    cap = _captura(monkeypatch, {"retorno": {"status": "OK", "contato": {
        "id": "610661344", "codigo": "12527"}}})
    r = tiny_client.obter_contato(610661344)
    assert r.ok and r.id == 610661344
    assert cap["url"].endswith("/contato.obter.php")


def test_obter_contato_bruto_devolve_o_contato(monkeypatch, ativa):
    _captura(monkeypatch, {"retorno": {"status": "OK", "contato": {
        "id": "610661344", "codigo": "12527", "nome": "Filial"}}})
    atual = tiny_client.obter_contato_bruto(610661344)
    assert atual["codigo"] == "12527"


def test_obter_contato_bruto_devolve_none_quando_falha(monkeypatch, ativa):
    _captura(monkeypatch, {"retorno": {"status": "Erro", "codigo_erro": "20", "erros": []}})
    assert tiny_client.obter_contato_bruto(1) is None


def test_obter_contato_bruto_desligado_registra_pulado_sem_chamar(monkeypatch):
    monkeypatch.setattr(settings, "TINY_TOKEN", "")
    chamou = []
    monkeypatch.setattr(httpx, "post", lambda *a, **k: chamou.append(1))
    linhas = []
    monkeypatch.setattr(tiny_client, "registrar_log_integracao", lambda **kw: linhas.append(kw))
    assert tiny_client.obter_contato_bruto(1) is None
    assert chamou == []
    assert linhas and linhas[0]["status"] == "pulado" and linhas[0]["motivo"] == "desligado"


def test_obter_contato_bruto_sucesso_registra_no_log(monkeypatch, ativa):
    _captura(monkeypatch, {"retorno": {"status": "OK", "contato": {
        "id": "610661344", "codigo": "12527"}}})
    linhas = []
    monkeypatch.setattr(tiny_client, "registrar_log_integracao", lambda **kw: linhas.append(kw))
    tiny_client.obter_contato_bruto(610661344)
    assert linhas and linhas[0]["status"] == "sucesso"


def test_erro_de_rede_nao_propaga(monkeypatch, ativa):
    def explode(*a, **k):
        raise httpx.ConnectError("sem rede")

    monkeypatch.setattr(httpx, "post", explode)
    r = tiny_client.incluir_contato({"nome": "X"})
    assert not r.ok and r.deve_tentar_de_novo and "sem rede" in r.mensagem


def test_corpo_nao_json_nao_propaga(monkeypatch, ativa):
    class Bruto(FakeResp):
        def json(self):
            raise ValueError("nao e json")

    monkeypatch.setattr(httpx, "post", lambda *a, **k: Bruto({"x": 1}))
    r = tiny_client.pesquisar_contato("1")
    assert not r.ok


def test_registra_no_log_de_integracao(monkeypatch, ativa):
    _captura(monkeypatch, {"retorno": {"status": "OK", "registros": [
        {"registro": {"status": "OK", "id": 7}}]}})
    linhas = []
    monkeypatch.setattr(tiny_client, "registrar_log_integracao", lambda **kw: linhas.append(kw))
    tiny_client.incluir_contato({"nome": "Filial"})
    assert linhas and linhas[0]["integracao"] == "tiny" and linhas[0]["status"] == "sucesso"


def test_classificar_tipo_do_tiny():
    from app.core.log_integracao import classificar_tipo
    assert classificar_tipo("tiny", None) == "empresa_contato"
