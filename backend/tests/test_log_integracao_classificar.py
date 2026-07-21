from app.core.log_integracao import classificar_tipo, referencia_os_do_payload


def test_classificar_tipo():
    assert classificar_tipo("taskhs", "gestorhs") == "os_espelho"
    assert classificar_tipo("growthhs", "gestorhs.os") == "os_card"
    assert classificar_tipo("growthhs", "gestorhs.atrasados") == "atrasados"
    assert classificar_tipo("growthhs", "gestorhs.calibracao") == "vencendo"
    assert classificar_tipo("growthhs", None) == "desconhecido"


def test_referencia_os_do_payload():
    assert referencia_os_do_payload("os_card", {"external_id": "10853"}) == 10853
    assert referencia_os_do_payload("os_espelho", {"external_id": "42"}) == 42
    assert referencia_os_do_payload("vencendo", {"external_id": "7794:2027-07-21"}) is None
    assert referencia_os_do_payload("os_card", {"external_id": "abc"}) is None
    assert referencia_os_do_payload("os_card", None) is None
