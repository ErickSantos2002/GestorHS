import pytest

from app.core import enderecos

RESULTADO_CEP = {"cep": "50030230", "endereco": "Cais do Apolo",
                 "municipio": "Recife", "estado": "PE"}
RESULTADO_CNPJ = {"documento": "36312056000552", "nome": "Acme Ltda",
                  "endereco": "Rua X, 10", "municipio": "Recife", "estado": "PE",
                  "cep": "50030230", "situacao": "ATIVA"}


@pytest.fixture()
def fingir_busca(monkeypatch):
    """Troca as funcoes de I/O por fakes — o endpoint nunca sai para a rede."""
    import app.api.integracoes_externas as mod

    def _aplicar(*, cep=None, cnpj=None):
        if cep is not None:
            monkeypatch.setattr(mod.enderecos_client, "buscar_cep", cep)
        if cnpj is not None:
            monkeypatch.setattr(mod.enderecos_client, "buscar_cnpj", cnpj)

    return _aplicar


def test_consultar_cep_devolve_o_mapeamento(client_admin, fingir_busca):
    fingir_busca(cep=lambda v: RESULTADO_CEP)
    r = client_admin.get("/integracoes/cep/50030-230")
    assert r.status_code == 200
    assert r.json() == RESULTADO_CEP


def test_consultar_cnpj_devolve_o_mapeamento(client_admin, fingir_busca):
    fingir_busca(cnpj=lambda v: RESULTADO_CNPJ)
    r = client_admin.get("/integracoes/cnpj/36312056000552")
    assert r.status_code == 200
    assert r.json() == RESULTADO_CNPJ


def test_cep_invalido_vira_400(client_admin, fingir_busca):
    def _erro(v):
        raise enderecos.DocumentoInvalido("CEP deve ter 8 digitos")

    fingir_busca(cep=_erro)
    assert client_admin.get("/integracoes/cep/123").status_code == 400


def test_cep_inexistente_vira_404(client_admin, fingir_busca):
    def _erro(v):
        raise enderecos.NaoEncontrado("CEP nao encontrado")

    fingir_busca(cep=_erro)
    assert client_admin.get("/integracoes/cep/00000000").status_code == 404


def test_provedor_fora_vira_502(client_admin, fingir_busca):
    def _erro(v):
        raise enderecos.ProvedorIndisponivel("sem rede")

    fingir_busca(cnpj=_erro)
    r = client_admin.get("/integracoes/cnpj/36312056000552")
    assert r.status_code == 502
    assert "indispon" in r.json()["detail"]


def test_exige_autenticacao(client):
    assert client.get("/integracoes/cep/50030230").status_code == 401


def test_cota_estourada_vira_429(client_admin, fingir_busca):
    """Cota nao e' o servico fora do ar: 429 diz ao usuario que vale tentar de novo.

    Precisa vir de um teste proprio porque LimiteExcedido herda de
    ProvedorIndisponivel — trocar a ordem dos except no endpoint faria este
    caso voltar a sair como 502 sem quebrar nenhum outro teste.
    """
    def _estourou(v):
        raise enderecos.LimiteExcedido("cota do provedor excedida")

    fingir_busca(cnpj=_estourou)
    r = client_admin.get("/integracoes/cnpj/36312056000552")
    assert r.status_code == 429
