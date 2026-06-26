from datetime import datetime, timezone
from types import SimpleNamespace

from app.core import taskhs


def _ordem(**kw):
    base = dict(
        id=1234, cliente_nome="Cliente X", equipamento_descricao="Bafômetro",
        equipamento_serie="SN-987", prox_calibragem=None, obs=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_lista_da_fase_cobre_ativas_e_finalizada():
    assert taskhs.lista_da_fase(4) == "🚚 Expedição (Abrindo caixa)"
    assert taskhs.lista_da_fase(5) == "🔬Laboratório Calibração"
    assert taskhs.lista_da_fase(6) == "Serviços 🪛"
    assert taskhs.lista_da_fase(7) == "🚚 Expedição (Preparando para Envio)"
    assert taskhs.lista_da_fase(8) == "📮Correios"


def test_lista_da_fase_cancelada_e_desconhecida_none():
    assert taskhs.lista_da_fase(9) is None
    assert taskhs.lista_da_fase(999) is None


def test_montar_titulo_completo():
    assert taskhs.montar_titulo(_ordem()) == "OS #1234 · Cliente X · Bafômetro"


def test_montar_titulo_sem_descricao_usa_serie():
    o = _ordem(equipamento_descricao=None)
    assert taskhs.montar_titulo(o) == "OS #1234 · Cliente X · SN-987"


def test_montar_titulo_so_id_quando_resto_vazio():
    o = _ordem(cliente_nome=None, equipamento_descricao=None, equipamento_serie=None)
    assert taskhs.montar_titulo(o) == "OS #1234"


def test_montar_payload_campos_basicos():
    p = taskhs.montar_payload(_ordem(obs="veio sem maleta"), lista="L", arquivado=False)
    assert p["source"] == "gestorhs"
    assert p["external_id"] == "1234"
    assert p["board"] == "Serviço"
    assert p["list"] == "L"
    assert p["title"] == "OS #1234 · Cliente X · Bafômetro"
    assert p["description"] == "veio sem maleta"
    assert p["priority"] == "medium"
    assert p["archived"] is False
    assert p["due_date"] is None


def test_montar_payload_due_date_de_prox_calibragem():
    o = _ordem(prox_calibragem=datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc))
    assert taskhs.montar_payload(o, lista="L", arquivado=False)["due_date"] == "2026-07-10"


def test_montar_payload_arquivado_true():
    assert taskhs.montar_payload(_ordem(), lista="L", arquivado=True)["archived"] is True


def test_lista_da_fase_financeiro():
    from app.core import taskhs
    assert taskhs.lista_da_fase(10) == "💰 Financeiro"
