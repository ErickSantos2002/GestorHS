from datetime import date, datetime, timezone
from types import SimpleNamespace as NS

from app.core.growthhs_os import montar_card_os


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


def _ordem(**kw):
    base = dict(
        id=9001,
        equipamento_descricao="HS PASS - IBLOW",
        equipamento_serie="SN-123",
        calib_situacao="Aprovado",
        calib_cert="CERT-2026-001",
        prox_calibragem=datetime(2027, 1, 20, 12, 0, tzinfo=timezone.utc),
        tipo_servico="C",
    )
    base.update(kw)
    return NS(**base)


def _device(**kw):
    base = dict(serial_number="SN-123", model="HS PASS - IBLOW",
                alcohol_module=None, next_recalibration_date="2027-01-20")
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# source / external_id / board_id
# ---------------------------------------------------------------------------

def test_source_external_id_board_id():
    card = montar_card_os(_ordem(id=9001), _cliente(), _device(), board_id=3, hoje=date(2026, 7, 20))
    assert card["source"] == "gestorhs.os"
    assert card["external_id"] == "9001"
    assert card["board_id"] == 3


# ---------------------------------------------------------------------------
# title
# ---------------------------------------------------------------------------

def test_titulo_com_os_cliente_equipamento_serie():
    ordem = _ordem(id=42, equipamento_descricao="HS PASS", equipamento_serie="SN-999")
    cliente = _cliente(nome="ACME Ltda")
    card = montar_card_os(ordem, cliente, _device(), board_id=1, hoje=date(2026, 7, 20))
    assert card["title"] == "OS #42 · ACME Ltda · HS PASS SN-999"


def test_titulo_truncado_em_500_quando_nome_cliente_gigante():
    nome_gigante = "Cliente " * 100  # 800 caracteres, bem maior que o limite
    ordem = _ordem(id=1)
    cliente = _cliente(nome=nome_gigante)
    card = montar_card_os(ordem, cliente, _device(), board_id=1, hoje=date(2026, 7, 20))
    assert len(card["title"]) == 500


# ---------------------------------------------------------------------------
# due_date — bug real de 422 (data pura recusada pelo Pydantic v2)
# ---------------------------------------------------------------------------

def test_due_date_e_hoje_mais_dois_dias_com_t():
    card = montar_card_os(_ordem(), _cliente(), _device(), board_id=1, hoje=date(2026, 7, 18))
    assert card["due_date"] == "2026-07-20T00:00:00"


# ---------------------------------------------------------------------------
# description
# ---------------------------------------------------------------------------

def test_descricao_com_situacao_certificado_e_proxima_calibracao():
    ordem = _ordem(calib_situacao="Aprovado", calib_cert="CERT-001",
                    prox_calibragem=datetime(2027, 1, 20, tzinfo=timezone.utc))
    card = montar_card_os(ordem, _cliente(), _device(), board_id=1, hoje=date(2026, 7, 20))
    assert "Aprovado" in card["description"]
    assert "CERT-001" in card["description"]
    assert "20/01/2027" in card["description"]


def test_descricao_omite_partes_ausentes_sem_none_no_texto():
    ordem = _ordem(calib_situacao=None, calib_cert=None, prox_calibragem=None)
    card = montar_card_os(ordem, _cliente(), _device(), board_id=1, hoje=date(2026, 7, 20))
    assert "None" not in card["description"]


# ---------------------------------------------------------------------------
# devices
# ---------------------------------------------------------------------------

def test_devices_tem_exatamente_um_item():
    device = _device(serial_number="SN-777")
    card = montar_card_os(_ordem(), _cliente(), device, board_id=1, hoje=date(2026, 7, 20))
    assert card["devices"] == [device]


# ---------------------------------------------------------------------------
# contact
# ---------------------------------------------------------------------------

def test_contact_ausente_quando_cliente_sem_contato():
    card = montar_card_os(_ordem(), _cliente_sem_contato(), _device(), board_id=1, hoje=date(2026, 7, 20))
    assert card["contact"] is None


def test_contact_presente_quando_cliente_tem_contato():
    card = montar_card_os(_ordem(), _cliente(contato="Marcos"), _device(), board_id=1, hoje=date(2026, 7, 20))
    assert card["contact"] is not None
    assert card["contact"]["name"] == "Marcos"


# ---------------------------------------------------------------------------
# business_info
# ---------------------------------------------------------------------------

def test_business_info_com_os_id():
    ordem = _ordem(id=555, tipo_servico="M")
    card = montar_card_os(ordem, _cliente(), _device(), board_id=1, hoje=date(2026, 7, 20))
    assert card["business_info"]["os_id"] == 555
    assert card["business_info"]["origem"] == "os liberada do laboratorio"
    assert card["business_info"]["tipo_servico"] == "M"
