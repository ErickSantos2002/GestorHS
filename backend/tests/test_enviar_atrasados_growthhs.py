"""Testes do script de backfill dos atrasados para o board Cobranca do GrowthHS.

Cobre `buscar_atrasados` (a consulta e suas exclusoes/regras), `processar`
(agrupamento + envio best-effort) e o comportamento de seguranca do `main()`
(sem --enviar nao manda nada; com --enviar mas integracao desligada aborta
cedo, antes de abrir sessao de banco).
"""
from datetime import date, timedelta

import pytest

from app.core.config import settings

ONTEM = date.today() - timedelta(days=1)
AMANHA = date.today() + timedelta(days=1)


def _cliente(db, id_, nome="Cliente Teste", contato="Fulano"):
    from app.models import Cliente
    c = Cliente(id=id_, nome=nome, contato=contato, cgc="12345678000199")
    db.add(c); db.commit(); db.refresh(c)
    return c


def _equipamento(db, id_, descricao):
    from app.models import Equipamento
    eq = Equipamento(id=id_, descricao=descricao)
    db.add(eq); db.commit(); db.refresh(eq)
    return eq


def _ec(db, *, cliente_id, equipamento_id, serie, prox_calibragem, ativo=True):
    from app.models import EquipamentoCliente
    ec = EquipamentoCliente(cliente=cliente_id, equipamento=equipamento_id, serie=serie,
                             prox_calibragem=prox_calibragem, ativo=ativo)
    db.add(ec); db.commit(); db.refresh(ec)
    return ec


def _mundo_dois_clientes(db):
    """Dois clientes normais, cada um com um equipamento vencido — para os
    testes de processar()/envio (sem_contato/elo nao importam aqui)."""
    eq_normal = _equipamento(db, 100, "HS PASS - IBLOW")
    c1 = _cliente(db, 10, nome="Cliente A")
    c2 = _cliente(db, 11, nome="Cliente B")
    _ec(db, cliente_id=c1.id, equipamento_id=eq_normal.id, serie="SN-A", prox_calibragem=ONTEM)
    _ec(db, cliente_id=c2.id, equipamento_id=eq_normal.id, serie="SN-B", prox_calibragem=ONTEM)
    return c1, c2


# ---------------------------------------------------------------------------
# buscar_atrasados
# ---------------------------------------------------------------------------

def test_equipamento_vencido_de_cliente_normal_entra(db_session):
    from app.scripts.enviar_atrasados_growthhs import buscar_atrasados
    eq = _equipamento(db_session, 100, "HS PASS - IBLOW")
    cli = _cliente(db_session, 10)
    _ec(db_session, cliente_id=cli.id, equipamento_id=eq.id, serie="SN-ENTRA", prox_calibragem=ONTEM)

    linhas = buscar_atrasados(db_session)

    assert len(linhas) == 1
    assert linhas[0]["ec"].serie == "SN-ENTRA"
    assert linhas[0]["cliente_id"] == cli.id
    assert linhas[0]["elo"] is None


def test_phoebus_vencido_nao_entra(db_session):
    from app.scripts.enviar_atrasados_growthhs import buscar_atrasados
    eq_phoebus = _equipamento(db_session, settings.EQUIPAMENTO_PHOEBUS_ID, "Phoebus")
    cli = _cliente(db_session, 10)
    _ec(db_session, cliente_id=cli.id, equipamento_id=eq_phoebus.id, serie="PHO-1", prox_calibragem=ONTEM)

    linhas = buscar_atrasados(db_session)

    assert linhas == []


def test_ebs_vencido_nao_entra(db_session):
    from app.scripts.enviar_atrasados_growthhs import buscar_atrasados
    eq_ebs = _equipamento(db_session, settings.EQUIPAMENTO_EBS_ID, "EBS")
    cli = _cliente(db_session, 10)
    _ec(db_session, cliente_id=cli.id, equipamento_id=eq_ebs.id, serie="EBS-1", prox_calibragem=ONTEM)

    linhas = buscar_atrasados(db_session)

    assert linhas == []


def test_equipamento_vencido_do_cliente_de_estoque_nao_entra(db_session):
    from app.scripts.enviar_atrasados_growthhs import buscar_atrasados
    eq = _equipamento(db_session, 100, "HS PASS - IBLOW")
    cli_estoque = _cliente(db_session, settings.CLIENTE_ESTOQUE_HS_ID, nome="Estoque HS")
    _ec(db_session, cliente_id=cli_estoque.id, equipamento_id=eq.id, serie="EST-1", prox_calibragem=ONTEM)

    linhas = buscar_atrasados(db_session)

    assert linhas == []


def test_equipamento_nao_vencido_nao_entra(db_session):
    from app.scripts.enviar_atrasados_growthhs import buscar_atrasados
    eq = _equipamento(db_session, 100, "HS PASS - IBLOW")
    cli = _cliente(db_session, 10)
    _ec(db_session, cliente_id=cli.id, equipamento_id=eq.id, serie="SN-FUTURO", prox_calibragem=AMANHA)

    linhas = buscar_atrasados(db_session)

    assert linhas == []


def test_equipamento_vencido_inativo_nao_entra(db_session):
    from app.scripts.enviar_atrasados_growthhs import buscar_atrasados
    eq = _equipamento(db_session, 100, "HS PASS - IBLOW")
    cli = _cliente(db_session, 10)
    _ec(db_session, cliente_id=cli.id, equipamento_id=eq.id, serie="SN-INATIVO",
        prox_calibragem=ONTEM, ativo=False)

    linhas = buscar_atrasados(db_session)

    assert linhas == []


def test_modulo_vencido_com_instalacao_aberta_traz_o_elo_do_phoebus(db_session):
    from app.scripts.enviar_atrasados_growthhs import buscar_atrasados
    from app.models import InstalacaoModulo

    cli = _cliente(db_session, 10)
    eq_phoebus = _equipamento(db_session, settings.EQUIPAMENTO_PHOEBUS_ID, "Phoebus")
    eq_modulo = _equipamento(db_session, settings.EQUIPAMENTO_MODULO_ID, "Modulo de Calibracao")

    pho = _ec(db_session, cliente_id=cli.id, equipamento_id=eq_phoebus.id,
              serie="WATFR01-00340", prox_calibragem=None)
    mod = _ec(db_session, cliente_id=cli.id, equipamento_id=eq_modulo.id,
              serie="F005065", prox_calibragem=ONTEM)
    db_session.add(InstalacaoModulo(modulo=mod.id, phoebus=pho.id, entrou_em=date.today(),
                                     saiu_em=None, origem="teste"))
    db_session.commit()

    linhas = buscar_atrasados(db_session)

    assert len(linhas) == 1
    linha = linhas[0]
    assert linha["ec"].id == mod.id
    assert linha["elo"] is not None
    assert linha["elo"].serie == "WATFR01-00340"
    assert linha["elo"].descricao == "Phoebus"


def test_modulo_com_elo_end_to_end_produz_device_com_serie_do_phoebus(db_session):
    """Exercita a ponte elo -> montar_device: o ORM real expoe
    `equipamento_descricao` (nao `.descricao`) — se a ponte nao existisse,
    montar_device(elo=...) estouraria AttributeError aqui."""
    from app.scripts.enviar_atrasados_growthhs import buscar_atrasados
    from app.core.growthhs_atrasados import agrupar_por_cliente, montar_card_atrasados
    from app.models import InstalacaoModulo

    cli = _cliente(db_session, 10)
    eq_phoebus = _equipamento(db_session, settings.EQUIPAMENTO_PHOEBUS_ID, "Phoebus")
    eq_modulo = _equipamento(db_session, settings.EQUIPAMENTO_MODULO_ID, "Modulo de Calibracao")

    pho = _ec(db_session, cliente_id=cli.id, equipamento_id=eq_phoebus.id,
              serie="WATFR01-00340", prox_calibragem=None)
    mod = _ec(db_session, cliente_id=cli.id, equipamento_id=eq_modulo.id,
              serie="F005065", prox_calibragem=ONTEM)
    db_session.add(InstalacaoModulo(modulo=mod.id, phoebus=pho.id, entrou_em=date.today(),
                                     saiu_em=None, origem="teste"))
    db_session.commit()

    linhas = buscar_atrasados(db_session)
    grupos = agrupar_por_cliente(linhas)
    card = montar_card_atrasados(grupos[0], date.today(), board_id=settings.HSGROWTH_BOARD_COBRANCA)

    dev = card["devices"][0]
    assert dev["serial_number"] == "WATFR01-00340"
    assert dev["model"] == "Phoebus"
    assert dev["alcohol_module"] == "F005065"


def test_modulo_sem_instalacao_aberta_nao_traz_elo(db_session):
    from app.scripts.enviar_atrasados_growthhs import buscar_atrasados
    cli = _cliente(db_session, 10)
    eq_modulo = _equipamento(db_session, settings.EQUIPAMENTO_MODULO_ID, "Modulo de Calibracao")
    _ec(db_session, cliente_id=cli.id, equipamento_id=eq_modulo.id, serie="MOD-SOLTO",
        prox_calibragem=ONTEM)

    linhas = buscar_atrasados(db_session)

    assert len(linhas) == 1
    assert linhas[0]["elo"] is None


# ---------------------------------------------------------------------------
# processar (agrupamento + envio best-effort)
# ---------------------------------------------------------------------------

def test_processar_sem_enviar_nao_chama_enviar_card_sync(db_session, monkeypatch):
    from app.scripts import enviar_atrasados_growthhs as script
    _mundo_dois_clientes(db_session)
    chamadas = []
    monkeypatch.setattr(script, "enviar_card_sync", lambda payload: chamadas.append(payload))

    resultado = script.processar(db_session, enviar=False)

    assert chamadas == []
    assert resultado["criados"] == 0
    assert resultado["existentes"] == 0
    assert resultado["falhas"] == 0
    assert len(resultado["grupos"]) == 2
    assert resultado["pendencias"] == []


def test_simulacao_monta_o_card_de_todo_grupo(db_session, monkeypatch):
    """A simulacao TEM que montar o payload de todos os clientes.

    Se a montagem ficasse atras do `--enviar`, um cliente com dado ruim passaria
    limpo na simulacao e so estouraria na carga real — esvaziando a protecao que
    o modo simulacao existe para dar.
    """
    from app.scripts import enviar_atrasados_growthhs as script
    _mundo_dois_clientes(db_session)
    montados = []
    real = script.montar_card_atrasados

    def espiao(grupo, data_carga, board_id):
        montados.append(grupo["cliente_id"])
        return real(grupo, data_carga, board_id)

    monkeypatch.setattr(script, "montar_card_atrasados", espiao)
    monkeypatch.setattr(script, "enviar_card_sync", lambda p: pytest.fail("nao deveria enviar"))

    resultado = script.processar(db_session, enviar=False)

    assert len(montados) == 2          # montou os dois, mesmo sem enviar
    assert resultado["falhas"] == 0


def test_simulacao_reporta_cliente_que_quebra_a_montagem(db_session, monkeypatch):
    """Dado ruim vira pendencia JA na simulacao, em vez de estourar na carga real."""
    from app.scripts import enviar_atrasados_growthhs as script
    _mundo_dois_clientes(db_session)

    def explode_no_primeiro(grupo, data_carga, board_id):
        if grupo["cliente_id"] == min(g["cliente_id"] for g in [grupo]):
            raise ValueError("cliente sem nome")
        return {}

    monkeypatch.setattr(script, "montar_card_atrasados", explode_no_primeiro)
    monkeypatch.setattr(script, "enviar_card_sync", lambda p: pytest.fail("nao deveria enviar"))

    resultado = script.processar(db_session, enviar=False)

    assert resultado["falhas"] == 2
    assert all("falha ao montar o card" in p["motivo"] for p in resultado["pendencias"])


def test_processar_com_enviar_chama_uma_vez_por_grupo(db_session, monkeypatch):
    from app.scripts import enviar_atrasados_growthhs as script
    _mundo_dois_clientes(db_session)
    chamadas = []

    def _fake(payload):
        chamadas.append(payload)
        return {"created": True}

    monkeypatch.setattr(script, "enviar_card_sync", _fake)

    resultado = script.processar(db_session, enviar=True)

    assert len(chamadas) == 2
    assert resultado["criados"] == 2
    assert resultado["existentes"] == 0
    assert resultado["falhas"] == 0


def test_processar_distingue_criado_de_existente_pela_resposta(db_session, monkeypatch):
    from app.scripts import enviar_atrasados_growthhs as script
    _mundo_dois_clientes(db_session)

    def _fake(payload):
        return {"created": payload["business_info"]["cliente_id"] == 10}

    monkeypatch.setattr(script, "enviar_card_sync", _fake)

    resultado = script.processar(db_session, enviar=True)

    assert resultado["criados"] == 1
    assert resultado["existentes"] == 1


def test_processar_falha_em_um_grupo_nao_interrompe_os_demais(db_session, monkeypatch):
    from app.scripts import enviar_atrasados_growthhs as script
    c1, c2 = _mundo_dois_clientes(db_session)
    chamadas = []

    def _fake(payload):
        chamadas.append(payload)
        if payload["business_info"]["cliente_id"] == c1.id:
            raise RuntimeError("boom")
        return {"created": True}

    monkeypatch.setattr(script, "enviar_card_sync", _fake)

    resultado = script.processar(db_session, enviar=True)

    assert len(chamadas) == 2  # o segundo grupo ainda foi tentado
    assert resultado["falhas"] == 1
    assert resultado["criados"] == 1
    assert len(resultado["pendencias"]) == 1
    assert resultado["pendencias"][0]["cliente_id"] == c1.id
    assert resultado["pendencias"][0]["motivo"] == "boom"
    assert resultado["pendencias"][0]["cliente"] == "Cliente A"
    assert resultado["pendencias"][0]["qtd_equipamentos"] == 1


def test_processar_limite_restringe_grupos_processados(db_session, monkeypatch):
    from app.scripts import enviar_atrasados_growthhs as script
    _mundo_dois_clientes(db_session)
    chamadas = []

    def _fake(payload):
        chamadas.append(payload)
        return {"created": True}

    monkeypatch.setattr(script, "enviar_card_sync", _fake)

    resultado = script.processar(db_session, enviar=True, limite=1)

    assert len(resultado["grupos"]) == 1
    assert len(chamadas) == 1


def test_processar_conta_clientes_sem_contato_e_modulos_sem_elo(db_session):
    from app.scripts import enviar_atrasados_growthhs as script

    eq_normal = _equipamento(db_session, 100, "HS PASS - IBLOW")
    eq_modulo = _equipamento(db_session, settings.EQUIPAMENTO_MODULO_ID, "Modulo de Calibracao")
    c_sem_contato = _cliente(db_session, 10, nome="Sem Contato", contato=None)
    c_com_contato = _cliente(db_session, 11, nome="Com Contato", contato="Fulano")

    _ec(db_session, cliente_id=c_sem_contato.id, equipamento_id=eq_normal.id,
        serie="SN-1", prox_calibragem=ONTEM)
    _ec(db_session, cliente_id=c_com_contato.id, equipamento_id=eq_modulo.id,
        serie="MOD-1", prox_calibragem=ONTEM)  # modulo sem instalacao aberta -> sem elo

    resultado = script.processar(db_session, enviar=False)

    assert resultado["sem_contato"] == 1
    assert resultado["sem_elo"] == 1


# ---------------------------------------------------------------------------
# main() — seguranca (default nao envia; aborta cedo se integracao desligada)
# ---------------------------------------------------------------------------

def test_main_aborta_cedo_se_integracao_desligada_e_enviar_passado(monkeypatch, capsys):
    from app.scripts import enviar_atrasados_growthhs as script

    monkeypatch.setattr(script, "integracao_ativa", lambda: False)

    def _boom():
        raise AssertionError("nao deveria abrir sessao de banco nem gravar CSV")

    monkeypatch.setattr(script, "SessionLocal", _boom)
    monkeypatch.setattr("sys.argv", ["enviar_atrasados_growthhs.py", "--enviar"])

    script.main()  # nao deve levantar (aborta com print, nao com excecao)

    saida = capsys.readouterr().out
    assert "desligada" in saida.lower()


def test_main_sem_enviar_nao_manda_nada_e_avisa_no_terminal(db_session, monkeypatch, tmp_path, capsys):
    from app.scripts import enviar_atrasados_growthhs as script
    _mundo_dois_clientes(db_session)
    monkeypatch.setattr(script, "SessionLocal", lambda: db_session)
    chamadas = []
    monkeypatch.setattr(script, "enviar_card_sync", lambda payload: chamadas.append(payload))
    caminho_csv = tmp_path / "pendencias.csv"
    monkeypatch.setattr(
        "sys.argv",
        ["enviar_atrasados_growthhs.py", "--pendencias", str(caminho_csv)],
    )

    script.main()

    assert chamadas == []
    assert caminho_csv.exists()
    saida = capsys.readouterr().out
    assert "nada" in saida.lower() or "simulacao" in saida.lower() or "nenhum" in saida.lower()


# ---------------------------------------------------------------------------
# CSV de pendencias
# ---------------------------------------------------------------------------

def test_escrever_csv_pendencias_tem_as_colunas_esperadas(tmp_path):
    import os
    from app.scripts.enviar_atrasados_growthhs import _escrever_csv_pendencias

    caminho = tmp_path / "sub" / "pend.csv"
    os.makedirs(caminho.parent, exist_ok=True)
    _escrever_csv_pendencias(str(caminho), [
        {"cliente_id": 1, "cliente": "ACME", "qtd_equipamentos": 2, "motivo": "boom"},
    ])

    conteudo = caminho.read_text(encoding="utf-8")
    assert "cliente_id,cliente,qtd_equipamentos,motivo" in conteudo
    assert "ACME" in conteudo and "boom" in conteudo
