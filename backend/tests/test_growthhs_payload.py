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


def test_cliente_address_com_todos_os_campos():
    """Endereco + numero + bairro todos presentes."""
    c = montar_cliente(_cliente(endereco="Rua X", numero=220, bairro="Centro"))
    assert c["address"] == "Rua X, 220, Centro"


def test_cliente_address_sem_numero():
    """Endereco + bairro, sem numero — nao deve haver dupla virgula."""
    c = montar_cliente(_cliente(endereco="Rua X", numero=None, bairro="Centro"))
    assert c["address"] == "Rua X, Centro"


def test_cliente_address_sem_bairro():
    """Endereco + numero, sem bairro."""
    c = montar_cliente(_cliente(endereco="Rua X", numero=220, bairro=None))
    assert c["address"] == "Rua X, 220"


def test_cliente_address_todos_ausentes():
    """Nenhum dos campos de endereco — retorna None."""
    c = montar_cliente(_cliente(endereco=None, numero=None, bairro=None))
    assert c["address"] is None


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


# --- limites de tamanho do schema do GrowthHS -------------------------------
# Medido na base real: 169 de 969 clientes tinham client.phone acima de 20
# caracteres (varios telefones no mesmo campo, separados por barra) e tomariam
# 422. O certo e pegar o PRIMEIRO telefone, nao truncar no meio do numero.

def test_phone_do_cliente_pega_o_primeiro_e_cabe_em_20():
    c = montar_cliente(_cliente(celular=None, whatsapp=None,
                                telefones="019 3984 9248 / 011 3709 2415"))
    assert c["phone"] == "019 3984 9248"
    assert len(c["phone"]) <= 20


def test_phone_do_contato_pega_o_primeiro_e_cabe_em_50():
    ct = montar_contato(_cliente(celular=None, whatsapp=None,
                                 telefones="062 3383-3944 / 3900 / (62) 9106-4423 / (62) 3383-3900"))
    assert ct["phone"] == "062 3383-3944"
    assert len(ct["phone"]) <= 50


def test_phone_sem_barra_fica_intacto():
    c = montar_cliente(_cliente(celular="11987654321"))
    assert c["phone"] == "11987654321"


def test_phone_unico_gigante_ainda_e_cortado_no_limite():
    """Ultima linha de defesa: um numero unico absurdo nao pode estourar o schema."""
    c = montar_cliente(_cliente(celular="1" * 40, whatsapp=None, telefones=None))
    assert len(c["phone"]) == 20
