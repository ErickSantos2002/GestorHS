from datetime import date
from types import SimpleNamespace as NS

from app.core.growthhs_vencendo import SOURCE_VENCENDO, montar_card_vencendo

AGOSTO = date(2026, 8, 1)


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
    card = montar_card_vencendo([_linha()], AGOSTO, board_id=2)
    assert card["source"] == "gestorhs.calibracao"
    assert SOURCE_VENCENDO == "gestorhs.calibracao"


def test_external_id_e_por_cliente_mais_competencia():
    """A chave NAO depende da data da execucao NEM do aparelho: e' o que faz a rodada
    do mes seguinte devolver `created: false` para a competencia ja varrida."""
    card = montar_card_vencendo(
        [_linha(ec_id=77, prox=date(2026, 8, 3)),
         _linha(ec_id=78, prox=date(2026, 8, 20))], AGOSTO, board_id=2)
    assert card["external_id"] == "512:2026-08"


def test_external_id_muda_com_a_competencia():
    setembro = montar_card_vencendo([_linha(prox=date(2026, 9, 4))],
                                    date(2026, 9, 1), board_id=2)
    assert setembro["external_id"] == "512:2026-09"


def test_titulo_traz_cliente_quantidade_e_mes_por_extenso():
    card = montar_card_vencendo(
        [_linha(ec_id=77, prox=date(2026, 8, 3)),
         _linha(ec_id=78, prox=date(2026, 8, 20))], AGOSTO, board_id=2)
    assert card["title"] == "Calibração vencendo · ACME Ltda · 2 aparelhos · agosto/2026"


def test_titulo_no_singular_com_um_aparelho():
    card = montar_card_vencendo([_linha()], AGOSTO, board_id=2)
    assert card["title"] == "Calibração vencendo · ACME Ltda · 1 aparelho · agosto/2026"


def test_descricao_lista_os_aparelhos_na_ordem_de_vencimento():
    card = montar_card_vencendo(
        [_linha(ec_id=78, serie="SN-B", prox=date(2026, 8, 20)),
         _linha(ec_id=77, serie="SN-A", prox=date(2026, 8, 3))], AGOSTO, board_id=2)
    assert card["description"] == (
        "2 aparelhos deste cliente com calibração vencendo em agosto/2026:\n\n"
        "- HS PASS - IBLOW série SN-A — vence 03/08/2026\n"
        "- HS PASS - IBLOW série SN-B — vence 20/08/2026"
    )


def test_descricao_do_modulo_com_elo_mostra_o_phoebus_e_o_modulo():
    """O cliente reconhece o APARELHO, nao o numero do modulo — mesmo criterio do
    `montar_device`."""
    elo = NS(serie="WATFR01-00340", descricao="Phoebus")
    card = montar_card_vencendo([_linha(serie="F005065", elo=elo, prox=date(2026, 8, 9))],
                                AGOSTO, board_id=2)
    assert ("- Phoebus série WATFR01-00340 (módulo F005065) — vence 09/08/2026"
            in card["description"])


def test_descricao_sem_serie_nao_deixa_serie_orfa():
    card = montar_card_vencendo([_linha(serie=None, prox=date(2026, 8, 9))],
                                AGOSTO, board_id=2)
    assert "- HS PASS - IBLOW — vence 09/08/2026" in card["description"]
    assert "série " not in card["description"]


def test_descricao_nao_traz_dias_restantes():
    """O card vive o mes inteiro: 'em 12 dias' envelheceria mentindo."""
    card = montar_card_vencendo([_linha(prox=date(2026, 8, 20))], AGOSTO, board_id=2)
    assert "dia(s)" not in card["description"]
    assert "vence em" not in card["description"]


def test_due_date_e_o_vencimento_mais_proximo_do_grupo():
    """Prazo do card = prazo do aparelho mais urgente. Datetime COMPLETO: data pura
    devolve 422 (Pydantic v2 do GrowthHS: `Optional[datetime]`)."""
    card = montar_card_vencendo(
        [_linha(ec_id=78, prox=date(2026, 8, 20)),
         _linha(ec_id=77, prox=date(2026, 8, 3))], AGOSTO, board_id=2)
    assert card["due_date"] == "2026-08-03T00:00:00"


def test_devices_traz_todos_os_aparelhos_do_grupo():
    card = montar_card_vencendo(
        [_linha(ec_id=77, serie="SN-A", prox=date(2026, 8, 3)),
         _linha(ec_id=78, serie="SN-B", prox=date(2026, 8, 20))], AGOSTO, board_id=2)
    assert [d["serial_number"] for d in card["devices"]] == ["SN-A", "SN-B"]


def test_device_usa_o_elo_quando_presente():
    elo = NS(serie="WATFR01-00340", descricao="Phoebus")
    card = montar_card_vencendo([_linha(serie="F005065", elo=elo)], AGOSTO, board_id=2)
    dev = card["devices"][0]
    assert dev["serial_number"] == "WATFR01-00340"
    assert dev["alcohol_module"] == "F005065"


def test_contact_ausente_quando_cliente_sem_contato():
    card = montar_card_vencendo([_linha(cliente=_cliente(contato=None))],
                                AGOSTO, board_id=2)
    assert card["contact"] is None


def test_client_montado_com_external_id_do_id_interno():
    card = montar_card_vencendo([_linha(cliente=_cliente(id=1, nome="ACME Ltda"))],
                                AGOSTO, board_id=2)
    assert card["client"]["external_id"] == "1"
    assert card["client"]["name"] == "ACME Ltda"


def test_business_info():
    card = montar_card_vencendo(
        [_linha(ec_id=78, prox=date(2026, 8, 20)),
         _linha(ec_id=77, prox=date(2026, 8, 3))], AGOSTO, board_id=2)
    assert card["business_info"] == {
        "origem": "calibracao vencendo",
        "acquisition_channel": "Importação (GestorHs)",
        "cliente_id": 512,
        "competencia": "2026-08",
        "qtd_aparelhos": 2,
        "equipamento_cliente_ids": [77, 78],
    }


def test_business_info_traz_o_canal_de_aquisicao():
    """O board de Cobranca do GrowthHS mostra `business_info.acquisition_channel` como
    "Canal de aquisicao", e o servico de integracao dele NAO preenche esse campo — quem
    manda e' o GestorHS. A string tem que bater EXATAMENTE com a opcao do select
    (`Importacao (GestorHs)`, com S minusculo em "GestorHs"); qualquer diferenca vira um
    valor fora da lista no dropdown."""
    card = montar_card_vencendo([_linha()], AGOSTO, board_id=2)
    assert card["business_info"]["acquisition_channel"] == "Importação (GestorHs)"


def test_board_id_repassado():
    card = montar_card_vencendo([_linha()], AGOSTO, board_id=7)
    assert card["board_id"] == 7
