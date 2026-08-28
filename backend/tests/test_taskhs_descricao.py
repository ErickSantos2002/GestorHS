from datetime import datetime, timezone
from types import SimpleNamespace

from app.core import taskhs


def _dt(y, m, d):
    return datetime(y, m, d, 12, 0, tzinfo=timezone.utc)


def _ordem(**kw):
    base = dict(
        id=1234, fase=8, cliente_nome="Cliente X",
        equipamento_descricao="Bafômetro", equipamento_serie="SN-987",
        equipamento_rel=SimpleNamespace(patrimonio="PAT-1"),
        tipo_servico="C",
        data_chegada=_dt(2026, 6, 22), condicao_chegada="bom estado",
        acessorios_presentes=["Bobinas", "Cabos USB"], pilhas=4, bocais=2,
        obs="veio sem maleta",
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


def test_obs1_tem_cabecalho_recebido_e_sem_titulo_interno():
    obs = taskhs.montar_obs(_ordem(), certificados=[{"tipo": "C", "url": "http://x/c"}])
    o1 = obs["obs1"]
    assert "Cliente: Cliente X" in o1
    assert "Aparelho: Bafômetro · Série SN-987 / Patr. PAT-1" in o1
    assert "Serviço: Calibração" in o1
    assert "Chegada: 22/06/2026 · Condição: bom estado" in o1
    assert "Acessórios: Bobinas, Cabos USB" in o1
    assert "Pilhas: 4 · Bocais: 2" in o1
    assert "Obs: veio sem maleta" in o1
    assert "📋 Recebido" not in o1  # título interno removido


def test_obs2_laboratorio_com_certificado_sem_titulo():
    obs = taskhs.montar_obs(_ordem(), certificados=[{"tipo": "C", "url": "http://x/c"}])
    o2 = obs["obs2"]
    assert "Resultado: APROVADO" in o2
    assert "Calibrado em: 23/06/2026 · Próxima: 10/07/2027" in o2
    assert "Certificado: 12345" in o2
    assert "Certificado de Calibração: http://x/c" in o2
    assert "🔬 Laboratório" not in o2


def test_obs3_posvendas():
    obs = taskhs.montar_obs(_ordem(), certificados=[])
    assert "Contato: João · (11) 99999-9999" in obs["obs3"]
    assert "Aceite: 24/06/2026" in obs["obs3"]


def test_obs5_preparando_endereco():
    obs = taskhs.montar_obs(_ordem(), certificados=[])
    assert "Enviar para: Rua X, 100 ap 2 · Centro · São Paulo/SP · CEP 01000000" in obs["obs5"]


def test_obs6_finalizada_rastreio():
    obs = taskhs.montar_obs(_ordem(), certificados=[])
    assert "Rastreio: BR123 · Postado em: 25/06/2026" in obs["obs6"]


def test_secoes_por_fase_recebido():
    # fase 4: só obs1 (Recebido); demais None
    o = _ordem(fase=4, aceite=False, data_aceite=None, cod_retorno=None, data_retorno=None)
    obs = taskhs.montar_obs(o, certificados=[])
    assert obs["obs1"] is not None
    assert obs["obs2"] is None  # sem certificados
    assert obs["obs3"] is None
    assert obs["obs4"] is None
    assert obs["obs5"] is None
    assert obs["obs6"] is None


def test_obs2_aparece_com_certificado_manutencao():
    o = _ordem(fase=6, cod_retorno=None, data_retorno=None)
    obs = taskhs.montar_obs(o, certificados=[{"tipo": "M", "url": "http://x/m"}])
    assert "Certificado de Manutenção: http://x/m" in obs["obs2"]


def test_telefone_pega_primeiro_nao_vazio():
    o = _ordem(fase=6, cliente_rel=SimpleNamespace(
        endereco=None, numero=None, complemento=None, bairro=None, municipio=None,
        estado=None, cep=None, contato="Maria", celular=None, whatsapp="(11) 8888",
        telefones="3333-3333"))
    obs = taskhs.montar_obs(o, certificados=[])
    assert "Contato: Maria · (11) 8888" in obs["obs3"]


def test_linhas_vazias_omitidas():
    o = _ordem(fase=4, condicao_chegada=None, acessorios_presentes=[], pilhas=0,
               bocais=0, obs=None, aceite=False, data_aceite=None,
               cod_retorno=None, data_retorno=None)
    obs = taskhs.montar_obs(o, certificados=[])
    assert "Chegada: 22/06/2026" in obs["obs1"]
    assert "Condição:" not in obs["obs1"]
    assert "Acessórios:" not in obs["obs1"]
    assert "Pilhas:" not in obs["obs1"]


def test_link_omitido_quando_url_none():
    o = _ordem(fase=6, cod_retorno=None, data_retorno=None)
    obs = taskhs.montar_obs(o, certificados=[{"tipo": "C", "url": None}])
    assert obs["obs2"] is not None
    assert "Certificado de Calibração:" not in obs["obs2"]


def test_obs4_financeiro_confirmado():
    obs = taskhs.montar_obs(_ordem(fase=7), certificados=[])
    assert "Pagamento: confirmado em 26/06/2026" in obs["obs4"]


def test_obs4_pendente_e_obs5_oculto_em_financeiro():
    o = _ordem(fase=10, pago=False, data_pagamento=None, cod_retorno=None, data_retorno=None)
    obs = taskhs.montar_obs(o, certificados=[])
    assert "Pagamento: pendente" in obs["obs4"]
    assert obs["obs5"] is None


def test_obs4_oculto_antes_da_fase():
    o = _ordem(fase=6, pago=False, data_pagamento=None, cod_retorno=None, data_retorno=None)
    obs = taskhs.montar_obs(o, certificados=[])
    assert obs["obs4"] is None


def test_obs4_com_nota_fiscal():
    o = _ordem(fase=10, pago=False, data_pagamento=None, cod_retorno=None, data_retorno=None,
               nota_fiscal="abc.pdf", nota_fiscal_numero="12345")
    obs = taskhs.montar_obs(o, certificados=[], nota_fiscal_url="http://x/nf")
    assert "- Nota fiscal: 12345" in obs["obs4"]
    assert "- NF em PDF: http://x/nf" in obs["obs4"]


def test_obs4_com_pdf_e_xml_da_nota():
    """O Financeiro anexa o par PDF+XML; os dois viram link no card."""
    o = _ordem(fase=10, pago=False, data_pagamento=None, cod_retorno=None, data_retorno=None,
               nota_fiscal="abc.pdf", nota_fiscal_xml="abc.xml", nota_fiscal_numero="12345")
    obs = taskhs.montar_obs(o, certificados=[], nota_fiscal_url="http://x/nf",
                            nota_fiscal_xml_url="http://x/nf/xml")
    assert "- NF em PDF: http://x/nf" in obs["obs4"]
    assert "- NF em XML: http://x/nf/xml" in obs["obs4"]


def test_obs4_so_xml_quando_nao_ha_pdf():
    """OS antiga so tem PDF; a nova so quebraria se um dos dois fosse obrigatorio."""
    o = _ordem(fase=10, pago=False, data_pagamento=None, cod_retorno=None, data_retorno=None,
               nota_fiscal=None, nota_fiscal_xml="abc.xml", nota_fiscal_numero="12345")
    obs = taskhs.montar_obs(o, certificados=[], nota_fiscal_url=None,
                            nota_fiscal_xml_url="http://x/nf/xml")
    assert "PDF" not in obs["obs4"]
    assert "- NF em XML: http://x/nf/xml" in obs["obs4"]


def test_obs4_nota_fiscal_sem_url_mostra_so_numero():
    o = _ordem(fase=10, pago=False, data_pagamento=None, cod_retorno=None, data_retorno=None,
               nota_fiscal="abc.pdf", nota_fiscal_numero="12345")
    obs = taskhs.montar_obs(o, certificados=[], nota_fiscal_url=None)
    linha = [l for l in obs["obs4"].splitlines() if "Nota fiscal" in l][0]
    assert linha.strip() == "- Nota fiscal: 12345"
