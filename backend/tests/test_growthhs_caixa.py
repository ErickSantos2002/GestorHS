"""Payload do card de CAIXA no GrowthHS.

O card é da caixa, nunca da OS — cada aparelho entra como um item de `devices[]`.
O construtor por OS existiu até set/2026 e saiu junto com o do TaskHS.
"""
from datetime import date
from types import SimpleNamespace

from app.core import growthhs_os


def _cliente(**kw):
    base = dict(id=512, nome="ACME Ltda", cgc="12345678000199", cpf=None,
                email="fin@acme.com", contato="Marcos", celular="11987654321",
                whatsapp=None, telefones="1133334444", endereco="Rua X", numero=220,
                bairro="Centro", municipio="Sao Paulo", estado="SP")
    base.update(kw)
    return SimpleNamespace(**base)


def _device(**kw):
    base = dict(serial_number="SN-123", model="HS PASS - IBLOW",
                alcohol_module=None, next_recalibration_date="2027-01-20")
    base.update(kw)
    return base


def test_card_caixa_lista_todos_devices():
    cx = SimpleNamespace(id=7)
    cli = _cliente(nome="ACME", cgc="00", email=None, contato=None, celular=None,
                   telefones=None, endereco=None, numero=None, bairro=None,
                   municipio=None, estado=None)
    devices = [_device(serial_number="S1", model="Baf", next_recalibration_date=None),
               _device(serial_number="S2", model="Baf", next_recalibration_date=None)]
    card = growthhs_os.montar_card_caixa(cx, cli, devices, 3, date(2026, 7, 22))
    assert card["external_id"] == "7"
    assert len(card["devices"]) == 2
    assert card["client"]["name"] == "ACME"


def test_source_e_board_id():
    card = growthhs_os.montar_card_caixa(SimpleNamespace(id=7), _cliente(), [_device()],
                                         3, date(2026, 7, 20))
    assert card["source"] == "gestorhs.os"
    assert card["board_id"] == 3


def test_titulo_com_caixa_cliente_e_contagem():
    card = growthhs_os.montar_card_caixa(SimpleNamespace(id=42), _cliente(nome="ACME Ltda"),
                                         [_device(), _device(serial_number="SN-2")],
                                         1, date(2026, 7, 20))
    assert card["title"] == "CX 42 · ACME Ltda · 2 aparelhos"


def test_titulo_no_singular_com_um_aparelho():
    card = growthhs_os.montar_card_caixa(SimpleNamespace(id=42), _cliente(nome="ACME Ltda"),
                                         [_device()], 1, date(2026, 7, 20))
    assert card["title"] == "CX 42 · ACME Ltda · 1 aparelho"


def test_titulo_truncado_em_500_quando_nome_cliente_gigante():
    nome_gigante = "Cliente " * 100  # 800 caracteres, bem maior que o limite
    card = growthhs_os.montar_card_caixa(SimpleNamespace(id=1), _cliente(nome=nome_gigante),
                                         [_device()], 1, date(2026, 7, 20))
    assert len(card["title"]) == 500


def test_due_date_e_hoje_mais_dois_dias_com_t():
    """Data pura da 422 no GrowthHS: `due_date` e' Optional[datetime] no schema de la
    e o Pydantic v2 recusa "YYYY-MM-DD" com "invalid datetime separator, expected `T`"."""
    card = growthhs_os.montar_card_caixa(SimpleNamespace(id=1), _cliente(), [_device()],
                                         1, date(2026, 7, 18))
    assert card["due_date"] == "2026-07-20T00:00:00"


def test_contact_ausente_quando_cliente_sem_contato():
    card = growthhs_os.montar_card_caixa(SimpleNamespace(id=1), _cliente(contato=None),
                                         [_device()], 1, date(2026, 7, 20))
    assert card["contact"] is None


def test_contact_presente_quando_cliente_tem_contato():
    card = growthhs_os.montar_card_caixa(SimpleNamespace(id=1), _cliente(contato="Marcos"),
                                         [_device()], 1, date(2026, 7, 20))
    assert card["contact"]["name"] == "Marcos"


def test_business_info_com_caixa_id():
    card = growthhs_os.montar_card_caixa(SimpleNamespace(id=555), _cliente(), [_device()],
                                         1, date(2026, 7, 20))
    assert card["business_info"]["caixa_id"] == 555
    assert card["business_info"]["origem"] == "caixa liberada do laboratorio"
