from types import SimpleNamespace
from app.core import taskhs


def _os(**kw):
    base = dict(id=1, cliente_nome="ACME", equipamento_descricao="Bafômetro",
                equipamento_serie="S1", desfecho_lab="concluido", fase=6,
                calib_situacao="Aprovado", calib_cert="C-1", prox_calibragem=None,
                equipamento_rel=SimpleNamespace(patrimonio=None),
                # Campos exigidos pelos helpers por-OS reutilizados em montar_obs_caixa
                # (_cabecalho, _sec_posvendas, _sec_financeiro, _sec_preparando, _sec_finalizada)
                # que acessam esses atributos diretamente (sem getattr).
                tipo_servico=None, cliente_rel=None, aceite=False, data_aceite=None,
                pago=False, data_pagamento=None, nota_fiscal_numero=None,
                cod_retorno=None, data_retorno=None)
    base.update(kw)
    return SimpleNamespace(**base)


def test_titulo_caixa_conta_aparelhos():
    cx = SimpleNamespace(id=7)
    t = taskhs.montar_titulo_caixa(cx, [_os(id=1), _os(id=2)])
    assert "CX 7" in t and "ACME" in t and "2 aparelho" in t


def test_obs2_lista_por_aparelho_com_sem_conserto():
    cx = SimpleNamespace(id=7)
    ordens = [_os(id=1, equipamento_serie="S1"),
              _os(id=2, equipamento_serie="S2", desfecho_lab="sem_conserto",
                  desfecho_lab_obs="carcaça trincada")]
    obs = taskhs.montar_obs_caixa(cx, ordens, certificados_por_os={1: [{"tipo": "C", "url": "http://x"}]},
                                  nota_fiscal_url=None)
    assert "S1" in obs["obs2"] and "S2" in obs["obs2"]
    assert "sem conserto" in obs["obs2"].lower()


def test_obs4_uma_linha_por_nota():
    """A caixa pode levar a nota do servico e a de remessa: a expedicao precisa
    dos dois pares de link, um por linha."""
    cx = SimpleNamespace(id=7, numero_proposta=None)
    obs = taskhs.montar_obs_caixa(
        cx, [_os(fase=10, pago=True)], certificados_por_os={},
        notas=[{"numero": "111", "pdf": "u1", "xml": "u2"},
               {"numero": "222", "pdf": "u3", "xml": "u4"}])
    assert "NF 111 — PDF: u1 · XML: u2" in obs["obs4"]
    assert "NF 222 — PDF: u3 · XML: u4" in obs["obs4"]


def test_obs4_cai_no_formato_legado_sem_notas():
    """Caixa antiga, sem linha na tabela nova, mantem o card que a expedicao ja
    conhece — alimentado pelas colunas de `ordens`."""
    cx = SimpleNamespace(id=7, numero_proposta=None)
    obs = taskhs.montar_obs_caixa(
        cx, [_os(fase=10, nota_fiscal_numero="999")], certificados_por_os={},
        nota_fiscal_url="u1", nota_fiscal_xml_url="u2")
    assert "Nota fiscal: 999" in obs["obs4"]
    assert "NF em PDF: u1" in obs["obs4"]
