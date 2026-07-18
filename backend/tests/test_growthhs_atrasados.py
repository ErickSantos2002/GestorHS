from datetime import date
from types import SimpleNamespace as NS

from app.core.growthhs_atrasados import agrupar_por_cliente, montar_card_atrasados


def _cliente(**kw):
    base = dict(id=512, nome="ACME Ltda", cgc="12345678000199", cpf=None,
                email="fin@acme.com", contato="Marcos", celular="11987654321",
                whatsapp=None, telefones="1133334444", endereco="Rua X", numero=220,
                bairro="Centro", municipio="Sao Paulo", estado="SP")
    base.update(kw)
    return NS(**base)


def _cliente_sem_contato(**kw):
    kw.setdefault("contato", None)
    return _cliente(**kw)


def _ec(id_, serie, prox_calibragem):
    return NS(id=id_, serie=serie, prox_calibragem=prox_calibragem)


def _linha(cliente_id, cliente, ec, equipamento_desc="HS PASS - IBLOW", elo=None):
    return {
        "cliente_id": cliente_id,
        "cliente": cliente,
        "ec": ec,
        "equipamento_desc": equipamento_desc,
        "elo": elo,
    }


# ---------------------------------------------------------------------------
# agrupar_por_cliente
# ---------------------------------------------------------------------------

def test_agrupa_por_cliente_com_contagem_correta():
    c1 = _cliente(id=1, nome="Cliente 1")
    c2 = _cliente(id=2, nome="Cliente 2")
    linhas = [
        _linha(1, c1, _ec(10, "SN-1", date(2026, 1, 10))),
        _linha(1, c1, _ec(11, "SN-2", date(2026, 2, 5))),
        _linha(2, c2, _ec(20, "SN-3", date(2026, 3, 1))),
    ]
    grupos = agrupar_por_cliente(linhas)
    assert len(grupos) == 2
    assert grupos[0]["cliente_id"] == 1
    assert len(grupos[0]["itens"]) == 2
    assert grupos[1]["cliente_id"] == 2
    assert len(grupos[1]["itens"]) == 1


def test_vencimento_mais_antigo_e_o_menor():
    c1 = _cliente(id=1)
    linhas = [
        _linha(1, c1, _ec(10, "SN-1", date(2026, 3, 10))),
        _linha(1, c1, _ec(11, "SN-2", date(2026, 1, 5))),
        _linha(1, c1, _ec(12, "SN-3", date(2026, 2, 1))),
    ]
    grupos = agrupar_por_cliente(linhas)
    assert grupos[0]["vencimento_mais_antigo"] == date(2026, 1, 5)


def test_itens_ordenados_pela_data_mais_antiga_primeiro_dentro_do_cliente():
    c1 = _cliente(id=1)
    linhas = [
        _linha(1, c1, _ec(10, "SN-1", date(2026, 3, 10))),
        _linha(1, c1, _ec(11, "SN-2", date(2026, 1, 5))),
        _linha(1, c1, _ec(12, "SN-3", date(2026, 2, 1))),
    ]
    grupos = agrupar_por_cliente(linhas)
    series = [item["ec"].serie for item in grupos[0]["itens"]]
    assert series == ["SN-2", "SN-3", "SN-1"]


def test_ordenacao_deterministica_independente_da_ordem_de_entrada():
    """Alimentar as linhas fora de ordem (clientes e itens embaralhados) deve
    produzir sempre a mesma saida: clientes por cliente_id, itens por data."""
    c1 = _cliente(id=1)
    c2 = _cliente(id=2)
    c3 = _cliente(id=3)
    linhas_embaralhadas = [
        _linha(3, c3, _ec(30, "SN-C", date(2026, 5, 1))),
        _linha(1, c1, _ec(11, "SN-B", date(2026, 2, 1))),
        _linha(2, c2, _ec(20, "SN-D", date(2026, 4, 1))),
        _linha(1, c1, _ec(10, "SN-A", date(2026, 1, 1))),
    ]

    grupos_1 = agrupar_por_cliente(linhas_embaralhadas)
    grupos_2 = agrupar_por_cliente(list(reversed(linhas_embaralhadas)))

    ids_1 = [g["cliente_id"] for g in grupos_1]
    ids_2 = [g["cliente_id"] for g in grupos_2]
    assert ids_1 == [1, 2, 3]
    assert ids_2 == [1, 2, 3]

    series_1 = [item["ec"].serie for item in grupos_1[0]["itens"]]
    series_2 = [item["ec"].serie for item in grupos_2[0]["itens"]]
    assert series_1 == ["SN-A", "SN-B"]
    assert series_2 == ["SN-A", "SN-B"]


def test_itens_com_mesma_data_ordenados_deterministicamente_por_id():
    """Quando dois aparelhos do mesmo cliente têm a mesma data de próxima calibragem,
    a ordem deve ser determinística (por id), independente da ordem de entrada."""
    c1 = _cliente(id=1)
    same_date = date(2026, 1, 15)

    # Primeira rodada: EC 11 antes de EC 10
    linhas_1 = [
        _linha(1, c1, _ec(11, "SN-B", same_date)),
        _linha(1, c1, _ec(10, "SN-A", same_date)),
    ]

    # Segunda rodada: EC 10 antes de EC 11 (reverso)
    linhas_2 = [
        _linha(1, c1, _ec(10, "SN-A", same_date)),
        _linha(1, c1, _ec(11, "SN-B", same_date)),
    ]

    grupos_1 = agrupar_por_cliente(linhas_1)
    grupos_2 = agrupar_por_cliente(linhas_2)

    # Ambos devem produzir a mesma sequência de IDs (10 antes de 11)
    ids_1 = [item["ec"].id for item in grupos_1[0]["itens"]]
    ids_2 = [item["ec"].id for item in grupos_2[0]["itens"]]

    assert ids_1 == [10, 11]
    assert ids_2 == [10, 11]


# ---------------------------------------------------------------------------
# montar_card_atrasados
# ---------------------------------------------------------------------------

def test_external_id_no_formato_cliente_data():
    c1 = _cliente(id=512)
    grupos = agrupar_por_cliente([_linha(512, c1, _ec(1, "SN-1", date(2026, 1, 1)))])
    card = montar_card_atrasados(grupos[0], date(2026, 7, 18), board_id=2)
    assert card["external_id"] == "512:2026-07-18"


def test_source_fixo():
    c1 = _cliente(id=1)
    grupos = agrupar_por_cliente([_linha(1, c1, _ec(1, "SN-1", date(2026, 1, 1)))])
    card = montar_card_atrasados(grupos[0], date(2026, 7, 18), board_id=2)
    assert card["source"] == "gestorhs.atrasados"


def test_due_date_e_o_vencimento_mais_antigo():
    c1 = _cliente(id=1)
    linhas = [
        _linha(1, c1, _ec(10, "SN-1", date(2026, 3, 10))),
        _linha(1, c1, _ec(11, "SN-2", date(2026, 1, 5))),
    ]
    grupos = agrupar_por_cliente(linhas)
    card = montar_card_atrasados(grupos[0], date(2026, 7, 18), board_id=2)
    # datetime COMPLETO: o schema do GrowthHS declara `Optional[datetime]` e o
    # Pydantic v2 recusa data pura ("invalid datetime separator, expected `T`").
    # Confirmado com um 422 real em 18/07/2026 — o contrato diz que aceita
    # "YYYY-MM-DD", mas nao aceita.
    assert card["due_date"] == "2026-01-05T00:00:00"


def test_titulo_singular_com_um_aparelho():
    c1 = _cliente(id=1, nome="ACME Ltda")
    grupos = agrupar_por_cliente([_linha(1, c1, _ec(1, "SN-1", date(2026, 1, 1)))])
    card = montar_card_atrasados(grupos[0], date(2026, 7, 18), board_id=2)
    assert card["title"] == "Calibração vencida · ACME Ltda · 1 aparelho"


def test_titulo_plural_com_varios_aparelhos():
    c1 = _cliente(id=1, nome="ACME Ltda")
    linhas = [
        _linha(1, c1, _ec(10, "SN-1", date(2026, 3, 10))),
        _linha(1, c1, _ec(11, "SN-2", date(2026, 1, 5))),
    ]
    grupos = agrupar_por_cliente(linhas)
    card = montar_card_atrasados(grupos[0], date(2026, 7, 18), board_id=2)
    assert card["title"] == "Calibração vencida · ACME Ltda · 2 aparelhos"


def test_devices_tem_um_item_por_equipamento():
    c1 = _cliente(id=1)
    linhas = [
        _linha(1, c1, _ec(10, "SN-1", date(2026, 3, 10)), equipamento_desc="HS PASS"),
        _linha(1, c1, _ec(11, "SN-2", date(2026, 1, 5)), equipamento_desc="HS PASS"),
        _linha(1, c1, _ec(12, "SN-3", date(2026, 2, 1)), equipamento_desc="HS PASS"),
    ]
    grupos = agrupar_por_cliente(linhas)
    card = montar_card_atrasados(grupos[0], date(2026, 7, 18), board_id=2)
    assert len(card["devices"]) == 3
    seriais = {d["serial_number"] for d in card["devices"]}
    assert seriais == {"SN-1", "SN-2", "SN-3"}


def test_devices_usa_o_elo_quando_presente():
    c1 = _cliente(id=1)
    elo = NS(serie="WATFR01-00340", descricao="Phoebus")
    linhas = [_linha(1, c1, _ec(1, "F005065", date(2026, 1, 1)), elo=elo)]
    grupos = agrupar_por_cliente(linhas)
    card = montar_card_atrasados(grupos[0], date(2026, 7, 18), board_id=2)
    dev = card["devices"][0]
    assert dev["serial_number"] == "WATFR01-00340"
    assert dev["alcohol_module"] == "F005065"


def test_contact_ausente_quando_cliente_sem_contato():
    c1 = _cliente_sem_contato(id=1)
    grupos = agrupar_por_cliente([_linha(1, c1, _ec(1, "SN-1", date(2026, 1, 1)))])
    card = montar_card_atrasados(grupos[0], date(2026, 7, 18), board_id=2)
    assert card["contact"] is None


def test_contact_presente_quando_cliente_tem_contato():
    c1 = _cliente(id=1, contato="Marcos")
    grupos = agrupar_por_cliente([_linha(1, c1, _ec(1, "SN-1", date(2026, 1, 1)))])
    card = montar_card_atrasados(grupos[0], date(2026, 7, 18), board_id=2)
    assert card["contact"] is not None
    assert card["contact"]["name"] == "Marcos"


def test_client_montado_a_partir_do_cliente_do_grupo():
    c1 = _cliente(id=1, nome="ACME Ltda")
    grupos = agrupar_por_cliente([_linha(1, c1, _ec(1, "SN-1", date(2026, 1, 1)))])
    card = montar_card_atrasados(grupos[0], date(2026, 7, 18), board_id=2)
    assert card["client"]["external_id"] == "1"
    assert card["client"]["name"] == "ACME Ltda"


def test_business_info():
    c1 = _cliente(id=1)
    linhas = [
        _linha(1, c1, _ec(10, "SN-1", date(2026, 3, 10))),
        _linha(1, c1, _ec(11, "SN-2", date(2026, 1, 5))),
    ]
    grupos = agrupar_por_cliente(linhas)
    card = montar_card_atrasados(grupos[0], date(2026, 7, 18), board_id=2)
    assert card["business_info"] == {
        "origem": "backfill atrasados",
        "cliente_id": 1,
        "qtd_equipamentos": 2,
    }


def test_description_traz_quantidade_e_vencimento_mais_antigo():
    c1 = _cliente(id=1)
    linhas = [
        _linha(1, c1, _ec(10, "SN-1", date(2026, 3, 10))),
        _linha(1, c1, _ec(11, "SN-2", date(2026, 1, 5))),
    ]
    grupos = agrupar_por_cliente(linhas)
    card = montar_card_atrasados(grupos[0], date(2026, 7, 18), board_id=2)
    assert "2" in card["description"]
    assert "05/01/2026" in card["description"]


def test_board_id_repassado():
    c1 = _cliente(id=1)
    grupos = agrupar_por_cliente([_linha(1, c1, _ec(1, "SN-1", date(2026, 1, 1)))])
    card = montar_card_atrasados(grupos[0], date(2026, 7, 18), board_id=7)
    assert card["board_id"] == 7
