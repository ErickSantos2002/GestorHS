"""Mapa fase -> lista do board. O payload em si e' testado em test_taskhs_caixa.py:
o card e' da caixa, nao da OS."""
from app.core import taskhs


def test_list_id_da_fase_cobre_ativas_e_finalizada():
    assert taskhs.list_id_da_fase(4) == 196
    assert taskhs.list_id_da_fase(5) == 197
    assert taskhs.list_id_da_fase(6) == 202
    assert taskhs.list_id_da_fase(7) == 208  # 📑 Notas Faturadas
    assert taskhs.list_id_da_fase(8) == 210


def test_list_id_da_fase_financeiro():
    assert taskhs.list_id_da_fase(10) == 205


def test_list_id_da_fase_cancelada_e_desconhecida_none():
    assert taskhs.list_id_da_fase(9) is None
    assert taskhs.list_id_da_fase(999) is None
