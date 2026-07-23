from datetime import date
from types import SimpleNamespace
from app.core import growthhs_os


def test_card_caixa_lista_todos_devices():
    cx = SimpleNamespace(id=7)
    cli = SimpleNamespace(id=1, nome="ACME", cgc="00", cpf=None, email=None, celular=None,
                          whatsapp=None, telefones=None, endereco=None, numero=None,
                          bairro=None, municipio=None, estado=None, contato=None)
    devices = [{"serial_number": "S1", "model": "Baf", "alcohol_module": None, "next_recalibration_date": None},
               {"serial_number": "S2", "model": "Baf", "alcohol_module": None, "next_recalibration_date": None}]
    card = growthhs_os.montar_card_caixa(cx, cli, devices, 3, date(2026, 7, 22))
    assert card["external_id"] == "7"
    assert len(card["devices"]) == 2
    assert card["client"]["name"] == "ACME"
