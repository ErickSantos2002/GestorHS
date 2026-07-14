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


def test_descricao_completa_finalizada():
    d = taskhs.montar_descricao(_ordem(), certificados=[{"tipo": "C", "url": "http://x/c"}])
    assert "Cliente: Cliente X" in d
    assert "Aparelho: Bafômetro · Série SN-987 / Patr. PAT-1" in d
    assert "Serviço: Calibração" in d
    assert "📋 Recebido" in d
    assert "Chegada: 22/06/2026 · Condição: bom estado" in d
    assert "Acessórios: Bobinas, Cabos USB" in d
    assert "Pilhas: 4 · Bocais: 2" in d
    assert "Obs: veio sem maleta" in d
    assert "🔬 Laboratório" in d
    assert "Resultado: APROVADO" in d
    assert "Calibrado em: 23/06/2026 · Próxima: 10/07/2027" in d
    assert "Certificado: 12345" in d
    assert "Certificado de Calibração: http://x/c" in d
    assert "🤝 Pós-Vendas" in d
    assert "Contato: João · (11) 99999-9999" in d
    assert "Aceite: 24/06/2026" in d
    assert "🚚 Preparando Retorno" in d
    assert "Enviar para: Rua X, 100 ap 2 · Centro · São Paulo/SP · CEP 01000000" in d
    assert "📮 Finalizada" in d
    assert "Rastreio: BR123 · Postado em: 25/06/2026" in d


def test_secoes_aparecem_por_fase():
    # Em Recebido (fase 4): só cabeçalho + Recebido; sem Pós-Vendas/Retorno/Finalizada
    o = _ordem(fase=4, aceite=False, data_aceite=None, cod_retorno=None, data_retorno=None)
    d = taskhs.montar_descricao(o, certificados=[])
    assert "📋 Recebido" in d
    assert "🤝 Pós-Vendas" not in d
    assert "🚚 Preparando Retorno" not in d
    assert "📮 Finalizada" not in d
    assert "🔬 Laboratório" not in d  # sem certificados


def test_laboratorio_aparece_com_certificado():
    o = _ordem(fase=6, cod_retorno=None, data_retorno=None)
    d = taskhs.montar_descricao(o, certificados=[{"tipo": "M", "url": "http://x/m"}])
    assert "🔬 Laboratório" in d
    assert "Certificado de Manutenção: http://x/m" in d


def test_telefone_pega_primeiro_nao_vazio():
    o = _ordem(fase=6, cliente_rel=SimpleNamespace(
        endereco=None, numero=None, complemento=None, bairro=None, municipio=None,
        estado=None, cep=None, contato="Maria", celular=None, whatsapp="(11) 8888",
        telefones="3333-3333"))
    d = taskhs.montar_descricao(o, certificados=[])
    assert "Contato: Maria · (11) 8888" in d


def test_linhas_vazias_omitidas():
    o = _ordem(fase=4, condicao_chegada=None, acessorios_presentes=[], pilhas=0,
               bocais=0, obs=None, aceite=False, data_aceite=None,
               cod_retorno=None, data_retorno=None)
    d = taskhs.montar_descricao(o, certificados=[])
    assert "Chegada: 22/06/2026" in d
    assert "Condição:" not in d
    assert "Acessórios:" not in d
    assert "Pilhas:" not in d


def test_link_omitido_quando_url_none():
    o = _ordem(fase=6, cod_retorno=None, data_retorno=None)
    d = taskhs.montar_descricao(o, certificados=[{"tipo": "C", "url": None}])
    assert "🔬 Laboratório" in d
    assert "Certificado de Calibração:" not in d


def test_montar_payload_usa_descricao_quando_passada():
    p = taskhs.montar_payload(_ordem(), lista="L", arquivado=False, descricao="RESUMO")
    assert p["description"] == "RESUMO"


def test_montar_payload_sem_descricao_mantem_obs():
    o = SimpleNamespace(id=1, cliente_nome=None, equipamento_descricao=None,
                        equipamento_serie=None, prox_calibragem=None, obs="apenas obs")
    p = taskhs.montar_payload(o, lista="L", arquivado=False)
    assert p["description"] == "apenas obs"


def test_secao_financeiro_confirmado():
    d = taskhs.montar_descricao(_ordem(fase=7), certificados=[])
    assert "💰 Financeiro" in d
    assert "Pagamento: confirmado em 26/06/2026" in d


def test_financeiro_pendente_e_preparando_oculto_durante_financeiro():
    # Em Financeiro (fase 10): mostra pagamento pendente, NAO mostra Preparando Retorno
    o = _ordem(fase=10, pago=False, data_pagamento=None, cod_retorno=None, data_retorno=None)
    d = taskhs.montar_descricao(o, certificados=[])
    assert "💰 Financeiro" in d
    assert "Pagamento: pendente" in d
    assert "🚚 Preparando Retorno" not in d


def test_financeiro_oculto_antes_da_fase():
    o = _ordem(fase=6, pago=False, data_pagamento=None, cod_retorno=None, data_retorno=None)
    d = taskhs.montar_descricao(o, certificados=[])
    assert "💰 Financeiro" not in d


def test_secao_financeiro_com_nota_fiscal():
    o = _ordem(fase=10, pago=False, data_pagamento=None, cod_retorno=None, data_retorno=None,
               nota_fiscal="abc.pdf", nota_fiscal_numero="12345")
    d = taskhs.montar_descricao(o, certificados=[], nota_fiscal_url="http://x/nf")
    assert "💰 Financeiro" in d
    assert "Nota fiscal: 12345 — http://x/nf" in d


def test_secao_financeiro_sem_nota_fiscal_omite_a_linha():
    o = _ordem(fase=10, pago=False, data_pagamento=None, cod_retorno=None, data_retorno=None)
    d = taskhs.montar_descricao(o, certificados=[])
    assert "💰 Financeiro" in d
    assert "Nota fiscal" not in d


def test_nota_fiscal_sem_url_mostra_so_o_numero():
    o = _ordem(fase=10, pago=False, data_pagamento=None, cod_retorno=None, data_retorno=None,
               nota_fiscal="abc.pdf", nota_fiscal_numero="12345")
    d = taskhs.montar_descricao(o, certificados=[], nota_fiscal_url=None)
    assert "Nota fiscal: 12345" in d
    assert "—" not in d.split("Nota fiscal: 12345")[1].split("\n")[0]
