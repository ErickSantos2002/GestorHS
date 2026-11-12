"""O padrao da proposta saiu do front (propostaDefaults.ts) para o servidor. A
fixture foi gerada do TS original: o HTML tem que sair byte a byte igual."""
import json
from pathlib import Path

import pytest

from app.core import proposta_padrao as pp

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "proposta_padrao_ts.json").read_text())


def test_observacao_igual_a_da_tela():
    assert pp.DEFAULT_NOTES == FIXTURE["observacoes"]


@pytest.mark.parametrize("caso", FIXTURE["casos"], ids=lambda c: repr(c["modelos"]))
def test_html_igual_ao_da_tela(caso):
    assert pp.outros_itens_padrao(caso["modelos"], caso["series"]) == caso["padrao"]
    assert pp.outros_itens_phoebus(caso["series"], "") == caso["phoebus"]


def test_27_ufs_e_frete_de_toda_regiao():
    assert len(pp.REGIAO_POR_UF) == 27
    assert set(pp.REGIAO_POR_UF.values()) == set(pp.FRETE_POR_REGIAO)


def test_rota(client_exp):
    caso = FIXTURE["casos"][3]  # com caracteres que precisam de escape
    r = client_exp.get("/propostas/padrao", params={"modelos": caso["modelos"], "series": caso["series"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["observacoes"] == FIXTURE["observacoes"]
    assert body["validade_dias"] == 30
    assert body["frete_por_regiao"] == {"Norte": 200, "Nordeste": 150, "Sul": 250, "Sudeste": 200, "Centro-Oeste": 200}
    assert body["regiao_por_uf"]["PE"] == "Nordeste"
    assert body["outros_itens"] == {"padrao": caso["padrao"], "phoebus": caso["phoebus"]}


def test_rota_sem_parametros(client_exp):
    body = client_exp.get("/propostas/padrao").json()
    assert body["outros_itens"]["padrao"] == FIXTURE["casos"][0]["padrao"]
