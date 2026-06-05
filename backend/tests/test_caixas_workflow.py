import pytest
from app.core import caixas_workflow as cw


def test_constantes():
    assert (cw.PENDENTE, cw.ABERTA, cw.FINALIZADA) == ("P", "A", "F")


def test_pode_vincular():
    assert cw.pode_vincular("P") is True
    assert cw.pode_vincular("A") is True
    assert cw.pode_vincular("F") is False


def test_proximo_status_valido():
    assert cw.proximo_status("P") == "A"
    assert cw.proximo_status("A") == "F"


def test_validar_transicao_ok():
    cw.validar_transicao("P", "A")   # não levanta
    cw.validar_transicao("A", "F")   # não levanta


def test_validar_transicao_invalida():
    with pytest.raises(ValueError):
        cw.validar_transicao("P", "F")
    with pytest.raises(ValueError):
        cw.validar_transicao("F", "A")
