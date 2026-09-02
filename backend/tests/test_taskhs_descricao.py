"""Seções (obs1…obs6) do card da CAIXA no TaskHS.

O card é da caixa; os aparelhos entram como linhas dentro das obs. Uma caixa de um
aparelho só — o caso mais comum — é o que exercita as seções de nível lote
(pós-vendas, financeiro, preparando, finalizada), que saem de uma OS representativa.
"""
from datetime import datetime, timezone
from types import SimpleNamespace

from app.core import taskhs


def _dt(y, m, d):
    return datetime(y, m, d, 12, 0, tzinfo=timezone.utc)


def _caixa(**kw):
    return SimpleNamespace(**{"id": 740, "numero_proposta": None, **kw})


def _ordem(**kw):
    base = dict(
        id=1234, fase=8, cliente_nome="Cliente X",
        equipamento_descricao="Bafômetro", equipamento_serie="SN-987",
        equipamento_rel=SimpleNamespace(patrimonio="PAT-1"),
        tipo_servico="C",
        desfecho_lab="concluido",
        calib_situacao="APROVADO", data_calibracao=_dt(2026, 6, 23),
        prox_calibragem=_dt(2027, 7, 10), calib_cert="12345",
        aceite=True, data_aceite=_dt(2026, 6, 24),
        cliente_rel=SimpleNamespace(
            endereco="Rua X", numero=100, complemento="ap 2", bairro="Centro",
            municipio="São Paulo", estado="SP", cep="01000000",
            contato="João", celular="(11) 99999-9999", whatsapp=None, telefones=None,
        ),
        cod_retorno="BR123", data_retorno=_dt(2026, 6, 25),
        pago=True, data_pagamento=_dt(2026, 6, 26),
        nota_fiscal=None, nota_fiscal_numero=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _obs(ordem=None, *, certificados=(), caixa=None, **kw):
    o = ordem if ordem is not None else _ordem()
    return taskhs.montar_obs_caixa(caixa or _caixa(), [o],
                                   certificados_por_os={o.id: list(certificados)}, **kw)


def test_obs1_tem_cabecalho_e_lista_de_aparelhos():
    o1 = _obs()["obs1"]
    assert "Cliente: Cliente X" in o1
    assert "Aparelho: Bafômetro · Série SN-987 / Patr. PAT-1" in o1
    assert "Serviço: Calibração" in o1
    assert "- Bafômetro / SN-987" in o1  # o aparelho da caixa, em bullet
    assert "📋 Recebido" not in o1  # sem título interno: a obs já é nomeada no TaskHS


def test_obs2_laboratorio_com_certificado():
    o2 = _obs(certificados=[{"tipo": "C", "url": "http://x/c"}])["obs2"]
    assert "SN-987" in o2
    assert "APROVADO" in o2
    assert "cert 12345" in o2
    assert "http://x/c" in o2


def test_obs3_posvendas():
    obs = _obs()
    assert "Contato: João · (11) 99999-9999" in obs["obs3"]
    assert "Aceite: 24/06/2026" in obs["obs3"]


def test_obs3_leva_a_proposta_da_caixa():
    obs = _obs(caixa=_caixa(numero_proposta=99), proposta_url="http://x/p/1")
    assert "Proposta #99: http://x/p/1" in obs["obs3"]


def test_obs5_preparando_endereco():
    assert "Enviar para: Rua X, 100 ap 2 · Centro · São Paulo/SP · CEP 01000000" in _obs()["obs5"]


def test_obs6_finalizada_rastreio():
    assert "Rastreio: BR123 · Postado em: 25/06/2026" in _obs()["obs6"]


def test_secoes_por_fase_recebido():
    # fase 4: só obs1 (cabeçalho + aparelhos); as de etapas seguintes ficam None
    o = _ordem(fase=4, aceite=False, data_aceite=None, cod_retorno=None, data_retorno=None,
               desfecho_lab="pendente", calib_situacao=None, calib_cert=None)
    obs = _obs(o)
    assert obs["obs1"] is not None
    assert obs["obs3"] is None
    assert obs["obs4"] is None
    assert obs["obs5"] is None
    assert obs["obs6"] is None


def test_telefone_pega_primeiro_nao_vazio():
    o = _ordem(fase=6, cliente_rel=SimpleNamespace(
        endereco=None, numero=None, complemento=None, bairro=None, municipio=None,
        estado=None, cep=None, contato="Maria", celular=None, whatsapp="(11) 8888",
        telefones="3333-3333"))
    assert "Contato: Maria · (11) 8888" in _obs(o)["obs3"]


def test_obs4_financeiro_confirmado():
    assert "Pagamento: confirmado em 26/06/2026" in _obs(_ordem(fase=7))["obs4"]


def test_obs4_pendente_e_obs5_oculto_em_financeiro():
    o = _ordem(fase=10, pago=False, data_pagamento=None, cod_retorno=None, data_retorno=None)
    obs = _obs(o)
    assert "Pagamento: pendente" in obs["obs4"]
    assert obs["obs5"] is None


def test_obs4_oculto_antes_da_fase():
    o = _ordem(fase=6, pago=False, data_pagamento=None, cod_retorno=None, data_retorno=None)
    assert _obs(o)["obs4"] is None


def test_obs4_com_nota_fiscal():
    o = _ordem(fase=10, pago=False, data_pagamento=None, cod_retorno=None, data_retorno=None,
               nota_fiscal="abc.pdf", nota_fiscal_numero="12345")
    obs = _obs(o, nota_fiscal_url="http://x/nf")
    assert "- Nota fiscal: 12345" in obs["obs4"]
    assert "- NF em PDF: http://x/nf" in obs["obs4"]


def test_obs4_com_pdf_e_xml_da_nota():
    """O Financeiro anexa o par PDF+XML; os dois viram link no card."""
    o = _ordem(fase=10, pago=False, data_pagamento=None, cod_retorno=None, data_retorno=None,
               nota_fiscal="abc.pdf", nota_fiscal_xml="abc.xml", nota_fiscal_numero="12345")
    obs = _obs(o, nota_fiscal_url="http://x/nf", nota_fiscal_xml_url="http://x/nf/xml")
    assert "- NF em PDF: http://x/nf" in obs["obs4"]
    assert "- NF em XML: http://x/nf/xml" in obs["obs4"]


def test_obs4_so_xml_quando_nao_ha_pdf():
    """OS antiga so tem PDF; a nova so quebraria se um dos dois fosse obrigatorio."""
    o = _ordem(fase=10, pago=False, data_pagamento=None, cod_retorno=None, data_retorno=None,
               nota_fiscal=None, nota_fiscal_xml="abc.xml", nota_fiscal_numero="12345")
    obs = _obs(o, nota_fiscal_url=None, nota_fiscal_xml_url="http://x/nf/xml")
    assert "PDF" not in obs["obs4"]
    assert "- NF em XML: http://x/nf/xml" in obs["obs4"]


def test_obs4_nota_fiscal_sem_url_mostra_so_numero():
    o = _ordem(fase=10, pago=False, data_pagamento=None, cod_retorno=None, data_retorno=None,
               nota_fiscal="abc.pdf", nota_fiscal_numero="12345")
    obs = _obs(o, nota_fiscal_url=None)
    linha = [l for l in obs["obs4"].splitlines() if "Nota fiscal" in l][0]
    assert linha.strip() == "- Nota fiscal: 12345"
