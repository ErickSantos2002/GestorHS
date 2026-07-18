from datetime import date

from app.core.elo_modulos import escolher_cadastro, parse_data, escolher_vencedor, resolver_elos


def _l(n, ap, mod, prox="2027-01-01 00:00:00", emp="ACME"):
    return {"linha": n, "serie_aparelho": ap, "serie_modulo": mod, "prox_calib": prox, "empresa": emp}


def test_parse_data():
    assert parse_data("2027-03-27 04:00:59").year == 2027
    assert parse_data("") is None
    assert parse_data(None) is None
    assert parse_data("nao é data") is None


def test_escolher_vencedor_maior_prox_calibracao():
    """Caso real F000876: a perdedora tem data de 2000 (lixo)."""
    a = _l(42, "WATFR01-00364", "F000876", "2026-09-28 11:01:40")
    b = _l(43, "WATFR01-00488", "F000876", "2000-11-24 07:46:30")
    assert escolher_vencedor([a, b]) is a
    assert escolher_vencedor([b, a]) is a


def test_escolher_vencedor_sem_data_perde():
    com = _l(1, "AP1", "M1", "2027-01-01 00:00:00")
    sem = _l(2, "AP2", "M1", "")
    assert escolher_vencedor([sem, com]) is com


def test_resolver_elos_casa_os_dois_lados():
    linhas = [_l(2, "AP1", "M1")]
    elos, pend = resolver_elos(linhas, {"AP1": 10}, {"M1": 20})
    assert elos == [{"linha": 2, "phoebus_id": 10, "modulo_id": 20}]
    assert pend == []


def test_resolver_elos_pendencia_quando_lado_nao_existe():
    linhas = [_l(2, "AP_X", "M1"), _l(3, "AP1", "M_X")]
    elos, pend = resolver_elos(linhas, {"AP1": 10}, {"M1": 20})
    assert elos == []
    motivos = sorted(p["motivo"] for p in pend)
    assert motivos == ["aparelho nao encontrado", "modulo nao encontrado"]


def test_resolver_elos_linha_sem_modulo_e_ignorada():
    """91 aparelhos da planilha nao tem modulo — nao e erro, nao vira pendencia."""
    elos, pend = resolver_elos([_l(2, "AP1", "")], {"AP1": 10}, {})
    assert elos == [] and pend == []


def test_resolver_elos_duplicado_vence_o_mais_recente():
    linhas = [
        _l(42, "AP1", "M1", "2026-09-28 11:01:40"),
        _l(43, "AP2", "M1", "2000-11-24 07:46:30"),
    ]
    elos, pend = resolver_elos(linhas, {"AP1": 10, "AP2": 11}, {"M1": 20})
    assert elos == [{"linha": 42, "phoebus_id": 10, "modulo_id": 20}]
    assert len(pend) == 1 and pend[0]["linha"] == 43
    assert "duplicado" in pend[0]["motivo"]


def test_resolver_elos_duplicado_vencedora_sem_aparelho_tambem_vira_pendencia():
    """A vencedora nao some silenciosamente: se o proprio aparelho dela nao
    existe em series_phoebus, ela GANHA sua propria pendencia, alem da
    'duplicado' da perdedora."""
    linhas = [
        _l(42, "AP_NAO_EXISTE", "M1", "2026-09-28 11:01:40"),
        _l(43, "AP2", "M1", "2000-11-24 07:46:30"),
    ]
    elos, pend = resolver_elos(linhas, {"AP2": 11}, {"M1": 20})
    assert elos == []
    assert len(pend) == 2
    motivos_por_linha = {p["linha"]: p["motivo"] for p in pend}
    assert motivos_por_linha[43] == "duplicado (modulo em outro aparelho mais recente)"
    assert motivos_por_linha[42] == "aparelho nao encontrado"


def test_resolver_elos_duplicado_vencedora_sem_modulo_tambem_vira_pendencia():
    """Mesma logica, mas o que falta e o proprio modulo da vencedora."""
    linhas = [
        _l(42, "AP1", "M_NAO_EXISTE", "2026-09-28 11:01:40"),
        _l(43, "AP2", "M_NAO_EXISTE", "2000-11-24 07:46:30"),
    ]
    elos, pend = resolver_elos(linhas, {"AP1": 10, "AP2": 11}, {})
    assert elos == []
    assert len(pend) == 2
    motivos_por_linha = {p["linha"]: p["motivo"] for p in pend}
    assert motivos_por_linha[43] == "duplicado (modulo em outro aparelho mais recente)"
    assert motivos_por_linha[42] == "modulo nao encontrado"


def test_escolher_vencedor_empate_exato_vence_a_primeira():
    a = _l(1, "AP1", "M1", "2027-01-01 00:00:00")
    b = _l(2, "AP2", "M1", "2027-01-01 00:00:00")
    assert escolher_vencedor([a, b]) is a
    assert escolher_vencedor([b, a]) is b


def test_escolher_vencedor_lista_vazia_devolve_none():
    assert escolher_vencedor([]) is None


def test_escolher_cadastro_ativo_vence_inativo():
    """Caso real WATFR01-00155: 3945 (inativo) vs 6382 (ativo) -> 6382."""
    inativo = {"id": 3945, "ativo": False, "prox_calibragem": None}
    ativo = {"id": 6382, "ativo": True, "prox_calibragem": None}
    assert escolher_cadastro([inativo, ativo])[0] is ativo
    assert escolher_cadastro([ativo, inativo])[0] is ativo


def test_escolher_cadastro_ativo_vence_inativo_caso_watfr01_00634():
    """Caso real WATFR01-00634: 4064 (inativo) vs 5130 (ativo) -> 5130."""
    inativo = {"id": 4064, "ativo": False, "prox_calibragem": date(2023, 1, 1)}
    ativo = {"id": 5130, "ativo": True, "prox_calibragem": None}
    assert escolher_cadastro([inativo, ativo])[0] is ativo


def test_escolher_cadastro_ambos_ativos_vence_maior_prox_calibragem():
    """Caso real WATFR01-00198: 5411 (2024-03-08) vs 5989 (2025-04-25) -> 5989."""
    antigo = {"id": 5411, "ativo": True, "prox_calibragem": date(2024, 3, 8)}
    recente = {"id": 5989, "ativo": True, "prox_calibragem": date(2025, 4, 25)}
    assert escolher_cadastro([antigo, recente])[0] is recente
    assert escolher_cadastro([recente, antigo])[0] is recente


def test_escolher_cadastro_data_nula_perde_para_qualquer_data():
    com_data = {"id": 1, "ativo": True, "prox_calibragem": date(2020, 1, 1)}
    sem_data = {"id": 2, "ativo": True, "prox_calibragem": None}
    assert escolher_cadastro([sem_data, com_data])[0] is com_data


def test_escolher_cadastro_empate_total_vence_maior_id():
    """Caso real WATFR01-73064: 7022 (2025-12-17) vs 7134 (2026-02-10) -> 7134."""
    a = {"id": 7022, "ativo": True, "prox_calibragem": date(2025, 12, 17)}
    b = {"id": 7134, "ativo": True, "prox_calibragem": date(2026, 2, 10)}
    assert escolher_cadastro([a, b])[0] is b
    assert escolher_cadastro([b, a])[0] is b


def test_escolher_cadastro_empate_exato_vence_maior_id():
    mesma_data = date(2026, 1, 1)
    menor = {"id": 10, "ativo": True, "prox_calibragem": mesma_data}
    maior = {"id": 20, "ativo": True, "prox_calibragem": mesma_data}
    assert escolher_cadastro([menor, maior])[0] is maior
    assert escolher_cadastro([maior, menor])[0] is maior


def test_escolher_cadastro_devolve_ordem_completa_do_melhor_pro_pior():
    """A lista ordenada inteira e' usada pra reportar os descartados no resumo."""
    pior = {"id": 1, "ativo": False, "prox_calibragem": None}
    melhor = {"id": 2, "ativo": True, "prox_calibragem": date(2026, 1, 1)}
    assert escolher_cadastro([pior, melhor]) == [melhor, pior]
