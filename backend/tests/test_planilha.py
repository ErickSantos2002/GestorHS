from datetime import date, datetime, timezone
from io import BytesIO

import pytest
from openpyxl import load_workbook

from app.core.planilha import Coluna, LIMITE_LINHAS, PlanilhaGrandeDemais, gerar_xlsx

COLUNAS = [
    Coluna("Codigo", "id", 10, "inteiro"),
    Coluna("Nome", "nome", 30),
    Coluna("Nascimento", "nasc", 14, "data"),
    Coluna("Criado em", "criado", 18, "datahora"),
    Coluna("Valor", "valor", 12, "numero"),
    Coluna("Ativo", "ativo", 8, "sim_nao"),
]


def _abrir(conteudo: bytes):
    return load_workbook(BytesIO(conteudo)).active


def test_cabecalho_e_titulo_da_aba():
    aba = _abrir(gerar_xlsx("Clientes", COLUNAS, [], "sem filtros"))
    assert aba.title == "Clientes"
    assert [c.value for c in aba[1]] == ["Codigo", "Nome", "Nascimento", "Criado em", "Valor", "Ativo"]
    assert aba["A1"].font.bold is True


def test_painel_congelado_e_autofiltro():
    aba = _abrir(gerar_xlsx("Clientes", COLUNAS, [{"id": 1}], "sem filtros"))
    assert aba.freeze_panes == "A2"
    # 6 colunas (A..F), cabecalho + 1 linha de dados
    assert aba.auto_filter.ref == "A1:F2"


def test_tipos_das_celulas_sao_reais_nao_texto():
    linha = {
        "id": 7, "nome": "Fulano", "nasc": date(2020, 3, 1),
        "criado": datetime(2021, 5, 2, 14, 30, tzinfo=timezone.utc),
        "valor": 1234.56, "ativo": True,
    }
    aba = _abrir(gerar_xlsx("X", COLUNAS, [linha], "sem filtros"))
    assert aba["A2"].value == 7
    assert aba["C2"].value == datetime(2020, 3, 1)
    assert aba["C2"].number_format == "DD/MM/YYYY"
    assert aba["D2"].number_format == "DD/MM/YYYY HH:MM"
    assert aba["E2"].value == pytest.approx(1234.56)
    assert aba["F2"].value == "Sim"


def test_datahora_com_fuso_perde_o_tzinfo():
    """Excel nao guarda fuso; openpyxl recusa datetime aware. A conversao e' nossa."""
    linha = {"criado": datetime(2021, 5, 2, 14, 30, tzinfo=timezone.utc)}
    aba = _abrir(gerar_xlsx("X", COLUNAS, [linha], "sem filtros"))
    assert aba["D2"].value == datetime(2021, 5, 2, 14, 30)
    assert aba["D2"].value.tzinfo is None


def test_nulo_vira_celula_vazia_nunca_travessao():
    aba = _abrir(gerar_xlsx("X", COLUNAS, [{"id": 1, "nome": None}], "sem filtros"))
    assert aba["B2"].value is None


def test_booleano_falso_vira_nao_e_nulo_continua_vazio():
    aba = _abrir(gerar_xlsx("X", COLUNAS, [{"ativo": False}, {"ativo": None}], "sem filtros"))
    assert aba["F2"].value == "Nao"
    assert aba["F3"].value is None


def test_campo_ausente_no_dict_nao_quebra():
    aba = _abrir(gerar_xlsx("X", COLUNAS, [{}], "sem filtros"))
    assert aba["A2"].value is None


def test_largura_das_colunas_vem_da_definicao():
    aba = _abrir(gerar_xlsx("X", COLUNAS, [], "sem filtros"))
    assert aba.column_dimensions["A"].width == 10
    assert aba.column_dimensions["B"].width == 30


def test_rodape_registra_os_filtros_depois_de_uma_linha_em_branco():
    aba = _abrir(gerar_xlsx("X", COLUNAS, [{"id": 1}], "Status: Vencido"))
    # linha 1 cabecalho, linha 2 dado, linha 3 em branco, linha 4 rodape
    assert aba["A3"].value is None
    assert "Status: Vencido" in aba["A4"].value


def test_acima_do_teto_levanta():
    with pytest.raises(PlanilhaGrandeDemais):
        gerar_xlsx("X", COLUNAS, [{"id": 1}] * (LIMITE_LINHAS + 1), "sem filtros")


def test_no_teto_exato_nao_levanta(monkeypatch):
    """Baixamos o teto em vez de gerar 50.000 linhas de verdade: a regra sob teste e'
    `len(linhas) > LIMITE_LINHAS`, que nao depende do volume, e escrever um xlsx de
    50k linhas levaria dezenas de segundos numa suite que roda a cada commit."""
    import app.core.planilha as mod
    monkeypatch.setattr(mod, "LIMITE_LINHAS", 3)
    conteudo = gerar_xlsx("X", [Coluna("Codigo", "id", 10, "inteiro")],
                          [{"id": 1}] * 3, "sem filtros")
    assert conteudo[:2] == b"PK"  # xlsx e' um zip
