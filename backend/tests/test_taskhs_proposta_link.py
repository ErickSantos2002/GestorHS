from types import SimpleNamespace

from app.core import taskhs


def _os(**kw):
    base = dict(id=1, cliente_nome="ACME", equipamento_descricao="Bafômetro",
                equipamento_serie="S1", desfecho_lab="concluido", fase=6,
                calib_situacao="Aprovado", calib_cert="C-1", prox_calibragem=None,
                equipamento_rel=SimpleNamespace(patrimonio=None),
                tipo_servico=None, cliente_rel=None, aceite=False, data_aceite=None,
                pago=False, data_pagamento=None, nota_fiscal_numero=None,
                cod_retorno=None, data_retorno=None)
    base.update(kw)
    return SimpleNamespace(**base)


def test_sec_posvendas_com_numero_proposta_e_url():
    o = _os()
    txt = taskhs._sec_posvendas(o, numero_proposta=123, proposta_url="http://x/publico/proposta/123?t=abc")
    assert "Proposta #123" in txt
    assert "/publico/proposta/" in txt


def test_sec_posvendas_sem_numero_proposta_nao_tem_linha():
    o = _os()
    txt = taskhs._sec_posvendas(o)
    assert txt is None or "Proposta #" not in txt


def test_obs3_caixa_com_numero_proposta_e_url():
    cx = SimpleNamespace(id=7, numero_proposta=123)
    ordens = [_os(id=1)]
    obs = taskhs.montar_obs_caixa(cx, ordens, certificados_por_os={},
                                   proposta_url="http://x/publico/proposta/123?t=abc")
    assert "Proposta #123" in obs["obs3"]
    assert "/publico/proposta/" in obs["obs3"]


def test_obs3_caixa_sem_numero_proposta_nao_tem_linha():
    cx = SimpleNamespace(id=7, numero_proposta=None)
    ordens = [_os(id=1)]
    obs = taskhs.montar_obs_caixa(cx, ordens, certificados_por_os={})
    assert obs["obs3"] is None or "Proposta #" not in obs["obs3"]


def test_obs3_caixa_sem_atributo_numero_proposta_nao_quebra():
    # Caixa "antiga" (fixture de outros testes) sem o campo numero_proposta setado
    cx = SimpleNamespace(id=7)
    ordens = [_os(id=1)]
    obs = taskhs.montar_obs_caixa(cx, ordens, certificados_por_os={})
    assert obs["obs3"] is None or "Proposta #" not in obs["obs3"]
