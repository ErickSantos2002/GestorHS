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


def test_referencia_e_de_caixa_pelo_titulo():
    """O card e' da caixa desde set/2026; linha antiga por OS se distingue pelo titulo."""
    from app.core.log_integracao import referencia_e_de_caixa
    assert referencia_e_de_caixa({"title": "CX 916 · ACME · 2 aparelhos"}) is True
    assert referencia_e_de_caixa({"title": "CX 916 · OS #10992 · ACME · Bafometro"}) is False
    assert referencia_e_de_caixa({"title": "OS #1234 · ACME · Bafometro"}) is False


def test_referencia_sem_payload_nao_e_de_caixa():
    """Pulo por modulo nao tem payload: a referencia foi gravada com o id da OS."""
    from app.core.log_integracao import referencia_e_de_caixa
    assert referencia_e_de_caixa(None) is False
    assert referencia_e_de_caixa({}) is False
    assert referencia_e_de_caixa({"external_id": "916"}) is False  # payload sem titulo
