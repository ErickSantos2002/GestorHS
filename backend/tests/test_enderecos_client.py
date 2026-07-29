"""Nenhum teste aqui toca a internet: httpx.get e' sempre monkeypatched."""
import httpx
import pytest

from app.core import enderecos
from app.integrations import enderecos_client


class RespostaFake:
    def __init__(self, status_code=200, dados=None):
        self.status_code = status_code
        self._dados = dados if dados is not None else {}

    def json(self):
        return self._dados


def _fingir(monkeypatch, roteador):
    """roteador: callable(url) -> RespostaFake, ou levanta para simular rede fora."""
    chamadas = []

    def _get(url, timeout=None):
        chamadas.append(url)
        return roteador(url)

    monkeypatch.setattr(enderecos_client.httpx, "get", _get)
    return chamadas


CEP_BRASILAPI = {"cep": "50030230", "state": "PE", "city": "RECIFE", "street": "CAIS DO APOLO"}
CEP_VIACEP = {"cep": "50030-230", "logradouro": "Cais do Apolo", "localidade": "Recife", "uf": "PE"}
ESPERADO_CEP = {"cep": "50030230", "endereco": "Cais do Apolo", "municipio": "Recife", "estado": "PE"}


def test_buscar_cep_usa_brasilapi_e_nao_chama_o_fallback(monkeypatch):
    chamadas = _fingir(monkeypatch, lambda url: RespostaFake(200, CEP_BRASILAPI))
    assert enderecos_client.buscar_cep("50030-230") == ESPERADO_CEP
    assert len(chamadas) == 1
    assert "brasilapi" in chamadas[0]


def test_buscar_cep_cai_no_viacep_quando_brasilapi_da_erro(monkeypatch):
    def roteador(url):
        if "brasilapi" in url:
            raise httpx.ConnectError("sem rede")
        return RespostaFake(200, CEP_VIACEP)

    chamadas = _fingir(monkeypatch, roteador)
    assert enderecos_client.buscar_cep("50030230") == ESPERADO_CEP
    assert len(chamadas) == 2
    assert "viacep" in chamadas[1]


def test_buscar_cep_cai_no_viacep_quando_brasilapi_da_404(monkeypatch):
    def roteador(url):
        return RespostaFake(404) if "brasilapi" in url else RespostaFake(200, CEP_VIACEP)

    chamadas = _fingir(monkeypatch, roteador)
    assert enderecos_client.buscar_cep("50030230") == ESPERADO_CEP
    assert len(chamadas) == 2


def test_buscar_cep_inexistente_nos_dois_levanta_nao_encontrado(monkeypatch):
    def roteador(url):
        return RespostaFake(404) if "brasilapi" in url else RespostaFake(200, {"erro": True})

    _fingir(monkeypatch, roteador)
    with pytest.raises(enderecos.NaoEncontrado):
        enderecos_client.buscar_cep("00000000")


def test_buscar_cep_com_os_dois_provedores_fora_levanta_indisponivel(monkeypatch):
    def roteador(url):
        raise httpx.ConnectError("sem rede")

    _fingir(monkeypatch, roteador)
    with pytest.raises(enderecos.ProvedorIndisponivel):
        enderecos_client.buscar_cep("50030230")


def test_buscar_cep_invalido_nao_sai_para_a_rede(monkeypatch):
    chamadas = _fingir(monkeypatch, lambda url: RespostaFake(200, CEP_BRASILAPI))
    with pytest.raises(enderecos.DocumentoInvalido):
        enderecos_client.buscar_cep("123")
    assert chamadas == []


def test_buscar_cnpj_mapeia_a_resposta(monkeypatch):
    dados = {"cnpj": "36312056000552", "razao_social": "ACME LTDA", "logradouro": "RUA X",
             "numero": "10", "municipio": "RECIFE", "uf": "PE", "cep": "50030230",
             "descricao_situacao_cadastral": "ATIVA"}
    chamadas = _fingir(monkeypatch, lambda url: RespostaFake(200, dados))
    r = enderecos_client.buscar_cnpj("36.312.056/0005-52")
    assert r["nome"] == "Acme Ltda"
    assert r["endereco"] == "Rua X, 10"
    assert r["situacao"] == "ATIVA"
    assert len(chamadas) == 1


def test_buscar_cnpj_404_levanta_nao_encontrado_sem_fallback(monkeypatch):
    chamadas = _fingir(monkeypatch, lambda url: RespostaFake(404))
    with pytest.raises(enderecos.NaoEncontrado):
        enderecos_client.buscar_cnpj("00000000000000")
    assert len(chamadas) == 1


def test_buscar_cnpj_erro_de_rede_levanta_indisponivel(monkeypatch):
    def roteador(url):
        raise httpx.ConnectError("sem rede")

    _fingir(monkeypatch, roteador)
    with pytest.raises(enderecos.ProvedorIndisponivel):
        enderecos_client.buscar_cnpj("36312056000552")


def test_buscar_cnpj_invalido_nao_sai_para_a_rede(monkeypatch):
    chamadas = _fingir(monkeypatch, lambda url: RespostaFake(200, {}))
    with pytest.raises(enderecos.DocumentoInvalido):
        enderecos_client.buscar_cnpj("123")
    assert chamadas == []
