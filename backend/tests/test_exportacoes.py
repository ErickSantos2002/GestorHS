from datetime import date, datetime

from app.core.exportacoes import (
    COLUNAS_CERTIFICADOS, COLUNAS_CLIENTES, COLUNAS_FROTA, COLUNAS_ORDENS,
    linha_cliente, linha_frota, linha_ordem, montar_rodape, nome_arquivo,
)


class _Fake:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def test_todo_campo_de_coluna_tem_titulo_e_largura():
    for colunas in (COLUNAS_CLIENTES, COLUNAS_FROTA, COLUNAS_ORDENS, COLUNAS_CERTIFICADOS):
        assert colunas, "conjunto de colunas vazio"
        for c in colunas:
            assert c.titulo and c.largura > 0


def test_nao_ha_campo_repetido_em_um_mesmo_conjunto():
    """Campo repetido significa duas colunas mostrando o mesmo dado — quase sempre
    um copiar-e-colar esquecido."""
    for colunas in (COLUNAS_CLIENTES, COLUNAS_FROTA, COLUNAS_ORDENS, COLUNAS_CERTIFICADOS):
        campos = [c.campo for c in colunas]
        assert len(campos) == len(set(campos)), campos


def test_linha_cliente_traz_os_campos_das_colunas():
    c = _Fake(id=1, nome="ACME", cgc="11222333000144", cpf=None, insc_est="123",
              endereco="Rua A", numero=10, complemento=None, bairro="Centro",
              municipio="Recife", estado="PE", cep="50000000", contato="Joao",
              email="a@b.c", telefones="8130000000", celular=None, whatsapp=None,
              datcad=date(2020, 1, 5), ativo=True)
    linha = linha_cliente(c)
    for coluna in COLUNAS_CLIENTES:
        assert coluna.campo in linha, coluna.campo
    assert linha["nome"] == "ACME"
    assert linha["ativo"] is True


def test_linha_frota_escreve_o_status_por_extenso():
    e = _Fake(id=3, cliente_nome="ACME", cliente_rel=_Fake(cgc="11222333000144"),
              equipamento_descricao="Alcotest", equipamento_rel=None, serie="S1",
              patrimonio=None, datacompra=None, ult_calibragem=None,
              prox_calibragem=date(2030, 1, 1), status_calibracao="em_dia",
              calib_cert="C-1", calib_situacao="Aprovado", os_atual=None, ativo=True)
    linha = linha_frota(e)
    assert linha["status_calibracao"] == "Em dia"
    assert linha["cliente_cnpj"] == "11222333000144"


def test_linha_frota_sem_cliente_rel_nao_quebra():
    e = _Fake(id=3, cliente_nome=None, cliente_rel=None, equipamento_descricao=None,
              equipamento_rel=None, serie=None, patrimonio=None, datacompra=None,
              ult_calibragem=None, prox_calibragem=None, status_calibracao="sem_data",
              calib_cert=None, calib_situacao=None, os_atual=None, ativo=False)
    linha = linha_frota(e)
    assert linha["cliente_cnpj"] is None
    assert linha["marca"] is None
    assert linha["status_calibracao"] == "Sem data"


def test_linha_ordem_traz_os_campos_das_colunas():
    o = _Fake(id=99, etiqueta="ETIQ-1", cliente_nome="ACME", cliente_rel=_Fake(cgc="11222333000144"),
              equipamento_descricao="Alcotest", equipamento_serie="S1",
              fase_descricao="Laboratorio", tipo_servico="C",
              data_chegada=datetime(2026, 1, 2, 9, 0), data_calibracao=None,
              data_retorno=None, data_entrega=None, prox_calibragem=None,
              calib_cert="C-9", calib_situacao=None, nota_fiscal_numero="123",
              valor=10, frete_envio=0, frete_retorno=0, pago=False, caixa=None,
              garantia=True)
    linha = linha_ordem(o)
    for coluna in COLUNAS_ORDENS:
        assert coluna.campo in linha, coluna.campo
    assert linha["tipo_servico"] == "Calibracao"


def test_rodape_lista_os_filtros_usados_e_a_hora():
    texto = montar_rodape({"Status": "Vencido", "Cliente": "ACME"},
                          datetime(2026, 8, 19, 15, 4))
    assert "Status: Vencido" in texto
    assert "Cliente: ACME" in texto
    assert "19/08/2026 15:04" in texto


def test_rodape_sem_filtro_diz_que_nao_houve_filtro():
    texto = montar_rodape({}, datetime(2026, 8, 19, 15, 4))
    assert "sem filtros" in texto.lower()


def test_rodape_ignora_filtro_vazio():
    texto = montar_rodape({"Status": "", "Cliente": None, "Busca": "abc"},
                          datetime(2026, 8, 19, 15, 4))
    assert "Status" not in texto
    assert "Cliente" not in texto
    assert "Busca: abc" in texto


def test_nome_do_arquivo_leva_a_data():
    assert nome_arquivo("equipamentos", date(2026, 8, 19)) == "equipamentos-2026-08-19.xlsx"
