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


class RespostaJsonInvalido:
    """Simula HTTP 200 com corpo que nao e JSON valido (resp.json() levanta)."""

    def __init__(self, status_code=200):
        self.status_code = status_code

    def json(self):
        raise ValueError("Expecting value: line 1 column 1 (char 0)")


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


def test_buscar_cep_cai_no_viacep_quando_brasilapi_da_5xx(monkeypatch):
    def roteador(url):
        return RespostaFake(500) if "brasilapi" in url else RespostaFake(200, CEP_VIACEP)

    chamadas = _fingir(monkeypatch, roteador)
    assert enderecos_client.buscar_cep("50030230") == ESPERADO_CEP
    assert len(chamadas) == 2
    assert "viacep" in chamadas[1]


def test_buscar_cep_com_corpo_invalido_levanta_indisponivel(monkeypatch):
    chamadas = _fingir(monkeypatch, lambda url: RespostaJsonInvalido(200))
    with pytest.raises(enderecos.ProvedorIndisponivel):
        enderecos_client._get_json(enderecos_client.URL_BRASILAPI_CEP.format(cep="50030230"))
    assert len(chamadas) == 1


# ── Cota estourada (HTTP 429) ────────────────────────────────────────────────
# A cota da BrasilAPI conta por IP e passa sozinha em segundos, entao vale uma
# segunda tentativa — diferente de provedor fora do ar, onde insistir so demora.

@pytest.fixture(autouse=True)
def _sem_pausa(monkeypatch):
    """Zera a pausa entre tentativas: o teste nao pode esperar de verdade."""
    monkeypatch.setattr(enderecos_client.time, "sleep", lambda _: None)


def test_buscar_cnpj_tenta_de_novo_quando_a_cota_estoura(monkeypatch):
    dados = {"cnpj": "36312056000552", "razao_social": "ACME LTDA", "municipio": "RECIFE",
             "uf": "PE", "cep": "50030230"}
    respostas = [RespostaFake(429), RespostaFake(200, dados)]
    chamadas = _fingir(monkeypatch, lambda url: respostas.pop(0))
    assert enderecos_client.buscar_cnpj("36312056000552")["nome"] == "Acme Ltda"
    assert len(chamadas) == 2


def test_buscar_cnpj_com_cota_estourada_duas_vezes_levanta_limite_excedido(monkeypatch):
    chamadas = _fingir(monkeypatch, lambda url: RespostaFake(429))
    with pytest.raises(enderecos.LimiteExcedido):
        enderecos_client.buscar_cnpj("36312056000552")
    assert len(chamadas) == 2, "tenta de novo uma vez so, nao entra em loop"


def test_buscar_cnpj_com_provedor_fora_nao_tenta_de_novo(monkeypatch):
    """Erro de rede nao passa sozinho: insistir so faria o usuario esperar o dobro."""
    def _fora(url):
        raise httpx.ConnectError("sem rede")
    chamadas = _fingir(monkeypatch, _fora)
    with pytest.raises(enderecos.ProvedorIndisponivel):
        enderecos_client.buscar_cnpj("36312056000552")
    assert len(chamadas) == 1


def test_buscar_cep_cai_no_viacep_quando_a_cota_da_brasilapi_estoura(monkeypatch):
    """LimiteExcedido herda de ProvedorIndisponivel, entao o fallback do CEP pega."""
    def _rotear(url):
        return RespostaFake(429) if "brasilapi" in url else RespostaFake(200, CEP_VIACEP)
    _fingir(monkeypatch, _rotear)
    assert enderecos_client.buscar_cep("50030230") == ESPERADO_CEP
