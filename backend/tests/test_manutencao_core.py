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


# O resumo e' um texto padrao unico: o aparelho e a frase de conformidade
# aparecem UMA vez, e so os servicos se repetem. Emendar uma frase inteira por
# servico repetia o aparelho e a conformidade a cada item e ficava enorme com
# tres ou mais.

def test_resumo_com_um_servico():
    assert compor_resumo("Mercury", "10301681", [("214", "Troca de solenoide/bomba")]) == (
        "Foi realizada a manutenção no equipamento Mercury / nº de série 10301681, "
        "em conformidade com os procedimentos técnicos da Health & Safety, "
        "referente ao serviço: 214 – Troca de solenoide/bomba."
    )


def test_resumo_com_varios_servicos_lista_todos_sem_repetir_o_resto():
    texto = compor_resumo("Mercury", "10301681", [
        ("214", "Troca de solenoide/bomba"),
        ("315", "Troca do Bluetooth - Mercury"),
        ("70", "Troca do botão ON/OFF"),
    ])
    assert texto == (
        "Foi realizada a manutenção no equipamento Mercury / nº de série 10301681, "
        "em conformidade com os procedimentos técnicos da Health & Safety, "
        "referente aos serviços: 214 – Troca de solenoide/bomba; "
        "315 – Troca do Bluetooth - Mercury; 70 – Troca do botão ON/OFF."
    )
    assert texto.count("em conformidade") == 1, "a frase de conformidade nao pode repetir"
    assert texto.count("Mercury / nº de série") == 1, "o aparelho nao pode repetir"


def test_resumo_usa_plural_so_com_mais_de_um():
    um = compor_resumo("X", "1", [("1", "A")])
    dois = compor_resumo("X", "1", [("1", "A"), ("2", "B")])
    assert "referente ao serviço:" in um
    assert "referente aos serviços:" in dois


def test_resumo_sem_servico_devolve_vazio():
    assert compor_resumo("Mercury", "10301681", []) == ""


def test_resumo_sem_codigo_mostra_so_a_descricao():
    """Servico cadastrado a mao pelo laboratorio pode nao ter codigo."""
    texto = compor_resumo("X", "1", [(None, "Servico sem codigo")])
    assert "referente ao serviço: Servico sem codigo." in texto
    assert "–" not in texto.split("referente ao serviço:")[1]


@pytest.mark.parametrize("modelo,serie,esperado", [
    ("", "10301681", "no equipamento nº de série 10301681,"),
    ("Mercury", "", "no equipamento Mercury,"),
    ("", "", "no equipamento não identificado,"),
])
def test_resumo_aguenta_aparelho_sem_modelo_ou_serie(modelo, serie, esperado):
    """Cadastro incompleto nao pode gerar frase quebrada tipo "equipamento  / nº de série ,"."""
    assert esperado in compor_resumo(modelo, serie, [("1", "A")])
