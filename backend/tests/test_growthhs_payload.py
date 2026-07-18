from datetime import date
from types import SimpleNamespace as NS

from app.core.growthhs_payload import montar_cliente, montar_contato, montar_device


def _cliente(**kw):
    base = dict(id=512, nome="ACME Ltda", cgc="12345678000199", cpf=None,
                email="fin@acme.com", contato="Marcos", celular="11987654321",
                whatsapp=None, telefones="1133334444", endereco="Rua X", numero=220,
                bairro="Centro", municipio="Sao Paulo", estado="SP")
    base.update(kw)
    return NS(**base)


def test_cliente_usa_id_como_external_id_nunca_documento():
    c = montar_cliente(_cliente())
    assert c["external_id"] == "512"          # string, e o id — nao o CNPJ
    assert c["name"] == "ACME Ltda"
    assert c["document"] == "12345678000199"
    assert c["city"] == "Sao Paulo" and c["state"] == "SP"


def test_cliente_sem_cnpj_usa_cpf():
    c = montar_cliente(_cliente(cgc=None, cpf="12345678901"))
    assert c["document"] == "12345678901"


def test_contato_none_quando_nao_ha_nome():
    assert montar_contato(_cliente(contato=None)) is None
    assert montar_contato(_cliente(contato="  ")) is None


def test_contato_prefere_celular():
    ct = montar_contato(_cliente())
    assert ct["name"] == "Marcos" and ct["phone"] == "11987654321"


def test_contato_cai_para_telefones_sem_celular():
    ct = montar_contato(_cliente(celular=None, whatsapp=None))
    assert ct["phone"] == "1133334444"


def test_device_sem_elo_usa_a_serie_do_proprio():
    ec = NS(serie="SN-4471", prox_calibragem=date(2027, 7, 30))
    d = montar_device(ec, "HS PASS - IBLOW")
    assert d["serial_number"] == "SN-4471"
    assert d["model"] == "HS PASS - IBLOW"
    assert d["alcohol_module"] is None
    assert d["next_recalibration_date"] == "2027-07-30"


def test_device_com_elo_manda_o_phoebus_no_serial_e_o_modulo_no_alcohol_module():
    """O ponto do elo: o cliente reconhece o APARELHO, nao o numero do modulo."""
    modulo = NS(serie="F005065", prox_calibragem=date(2026, 9, 8))
    elo = NS(serie="WATFR01-00340", descricao="Phoebus")
    d = montar_device(modulo, "Modulo de Calibracao ... PHOEBUS", elo=elo)
    assert d["serial_number"] == "WATFR01-00340"
    assert d["model"] == "Phoebus"
    assert d["alcohol_module"] == "F005065"
    assert d["next_recalibration_date"] == "2026-09-08"


def test_device_sem_data():
    ec = NS(serie="SN-1", prox_calibragem=None)
    assert montar_device(ec, "X")["next_recalibration_date"] is None
