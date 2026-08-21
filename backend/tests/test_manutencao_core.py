"""Composicao dos textos do Relatorio de Manutencao (FORM-LAB-010).

Os exemplos vem dos relatorios reais em docs/certificado-manutencao/.
"""
import pytest

from app.core.manutencao import compor_problema, compor_resumo


def test_um_servico_termina_em_ponto():
    assert compor_problema(["Troca da placa mãe"]) == "Troca da placa mãe."


def test_dois_servicos_ligados_por_e():
    assert compor_problema(["Troca de Pilha interna", "Troca do Bluetooth Mercury"]) == \
        "Troca de Pilha interna e Troca do Bluetooth Mercury."


def test_tres_servicos_usam_virgula_e_e_no_ultimo():
    assert compor_problema(["A", "B", "C"]) == "A, B e C."


def test_sem_servico_devolve_vazio():
    assert compor_problema([]) == ""


def test_ponto_final_ja_existente_nao_duplica():
    assert compor_problema(["Troca da placa mãe."]) == "Troca da placa mãe."


def test_espacos_em_branco_sao_ignorados():
    assert compor_problema(["  Troca da placa mãe  ", "", "   "]) == "Troca da placa mãe."


def test_resumo_junta_as_frases_na_ordem():
    assert compor_resumo(["Primeira frase.", "Segunda frase."]) == "Primeira frase. Segunda frase."


def test_resumo_garante_ponto_entre_as_frases():
    assert compor_resumo(["Primeira frase", "Segunda frase"]) == "Primeira frase. Segunda frase."


def test_resumo_sem_frases_devolve_vazio():
    assert compor_resumo([]) == ""


@pytest.mark.parametrize("frases", [[""], ["   "], ["", "  "]])
def test_resumo_ignora_frases_vazias(frases):
    assert compor_resumo(frases) == ""
