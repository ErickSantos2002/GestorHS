from datetime import date
from types import SimpleNamespace as NS

from app.core.growthhs_vencendo import SOURCE_VENCENDO, montar_card_vencendo


def _cliente(**kw):
    base = dict(id=512, nome="ACME Ltda", cgc="12345678000199", cpf=None,
                email="fin@acme.com", contato="Marcos", celular="11987654321",
                whatsapp=None, telefones="1133334444", endereco="Rua X", numero=220,
                bairro="Centro", municipio="Sao Paulo", estado="SP")
    base.update(kw)
    return NS(**base)


def _linha(cliente=None, ec_id=77, serie="SN-1", prox=date(2026, 8, 20),
           equipamento_desc="HS PASS - IBLOW", elo=None):
    cliente = cliente or _cliente()
    return {
        "cliente_id": cliente.id,
        "cliente": cliente,
        "ec": NS(id=ec_id, serie=serie, prox_calibragem=prox),
        "equipamento_desc": equipamento_desc,
        "elo": elo,
    }


def test_source_fixo():
    card = montar_card_vencendo(_linha(), date(2026, 7, 20), board_id=2)
    assert card["source"] == "gestorhs.calibracao"
    assert SOURCE_VENCENDO == "gestorhs.calibracao"


def test_external_id_e_por_aparelho_mais_ciclo():
    """A chave NAO pode depender da data da execucao: e' isso que torna o job
    diario idempotente. Rodar em dias diferentes gera o MESMO external_id."""
    linha = _linha(ec_id=77, prox=date(2026, 8, 20))
    card_seg = montar_card_vencendo(linha, date(2026, 7, 20), board_id=2)
    card_ter = montar_card_vencendo(linha, date(2026, 7, 21), board_id=2)
    assert card_seg["external_id"] == "77:2026-08-20"
    assert card_ter["external_id"] == "77:2026-08-20"


def test_titulo_traz_cliente_equipamento_e_serie():
    card = montar_card_vencendo(
        _linha(serie="F005065", equipamento_desc="HS PASS - IBLOW"),
        date(2026, 7, 20), board_id=2,
    )
    assert card["title"] == "Calibração vencendo · ACME Ltda · HS PASS - IBLOW F005065"


def test_due_date_e_datetime_completo():
    """Data pura devolve 422 (Pydantic v2 do GrowthHS: `Optional[datetime]`)."""
    card = montar_card_vencendo(_linha(prox=date(2026, 8, 20)), date(2026, 7, 20), board_id=2)
    assert card["due_date"] == "2026-08-20T00:00:00"


def test_um_unico_device_por_card():
    card = montar_card_vencendo(_linha(serie="SN-9"), date(2026, 7, 20), board_id=2)
    assert len(card["devices"]) == 1
    assert card["devices"][0]["serial_number"] == "SN-9"


def test_device_usa_o_elo_quando_presente():
    """Modulo com Phoebus vinculado: o cliente reconhece o APARELHO, entao a serie
    do card e' a do Phoebus e a do modulo vai em `alcohol_module`."""
    elo = NS(serie="WATFR01-00340", descricao="Phoebus")
    card = montar_card_vencendo(_linha(serie="F005065", elo=elo), date(2026, 7, 20), board_id=2)
    dev = card["devices"][0]
    assert dev["serial_number"] == "WATFR01-00340"
    assert dev["alcohol_module"] == "F005065"


def test_descricao_traz_dias_restantes_e_data():
    card = montar_card_vencendo(_linha(prox=date(2026, 8, 20)), date(2026, 7, 20), board_id=2)
    assert "31" in card["description"]
    assert "20/08/2026" in card["description"]


def test_contact_ausente_quando_cliente_sem_contato():
    card = montar_card_vencendo(_linha(cliente=_cliente(contato=None)),
                                date(2026, 7, 20), board_id=2)
    assert card["contact"] is None


def test_client_montado_com_external_id_do_id_interno():
    card = montar_card_vencendo(_linha(cliente=_cliente(id=1, nome="ACME Ltda")),
                                date(2026, 7, 20), board_id=2)
    assert card["client"]["external_id"] == "1"
    assert card["client"]["name"] == "ACME Ltda"


def test_business_info():
    card = montar_card_vencendo(_linha(ec_id=77, prox=date(2026, 8, 20)),
                                date(2026, 7, 20), board_id=2)
    assert card["business_info"] == {
        "origem": "calibracao vencendo",
        "cliente_id": 512,
        "equipamento_cliente_id": 77,
        "dias_para_vencer": 31,
    }


def test_board_id_repassado():
    card = montar_card_vencendo(_linha(), date(2026, 7, 20), board_id=7)
    assert card["board_id"] == 7
