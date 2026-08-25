from datetime import datetime, timezone
from types import SimpleNamespace

from app.core import taskhs


def _ordem(**kw):
    base = dict(
        id=1234, cliente_nome="Cliente X", equipamento_descricao="Bafômetro",
        equipamento_serie="SN-987", prox_calibragem=None, obs=None, caixa=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


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


def test_montar_titulo_completo():
    assert taskhs.montar_titulo(_ordem()) == "OS #1234 · Cliente X · Bafômetro"


def test_montar_titulo_com_caixa_comeca_pela_caixa():
    o = _ordem(caixa=740)
    assert taskhs.montar_titulo(o) == "CX 740 · OS #1234 · Cliente X · Bafômetro"


def test_montar_titulo_sem_descricao_usa_serie():
    o = _ordem(equipamento_descricao=None)
    assert taskhs.montar_titulo(o) == "OS #1234 · Cliente X · SN-987"


def test_montar_titulo_so_id_quando_resto_vazio():
    o = _ordem(cliente_nome=None, equipamento_descricao=None, equipamento_serie=None)
    assert taskhs.montar_titulo(o) == "OS #1234"


def test_montar_payload_campos_basicos():
    o = _ordem()
    p = taskhs.montar_payload(o, list_id=22, arquivado=False, obs={"obs1": "cab"})
    assert p["source"] == "gestorhs"
    assert p["external_id"] == "1234"
    assert p["list_id"] == 22
    assert p["title"] == "OS #1234 · Cliente X · Bafômetro"
    assert p["priority"] == "medium"
    assert p["archived"] is False
    assert p["due_date"] is None
    assert "board" not in p and "list" not in p and "description" not in p


def test_montar_payload_espalha_as_seis_obs():
    obs = {"obs1": "A", "obs2": "B", "obs6": "F"}
    p = taskhs.montar_payload(_ordem(), list_id=21, arquivado=False, obs=obs)
    assert p["obs1"] == "A"
    assert p["obs2"] == "B"
    assert p["obs3"] is None
    assert p["obs4"] is None
    assert p["obs5"] is None
    assert p["obs6"] == "F"


def test_montar_payload_due_date_de_prox_calibragem():
    o = _ordem(prox_calibragem=datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc))
    assert taskhs.montar_payload(o, list_id=22, arquivado=False, obs={})["due_date"] == "2026-07-10"


def test_montar_payload_arquivado_true():
    assert taskhs.montar_payload(_ordem(), list_id=22, arquivado=True, obs={})["archived"] is True
