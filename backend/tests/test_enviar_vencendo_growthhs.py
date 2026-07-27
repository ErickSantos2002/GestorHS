import sys
from datetime import date, timedelta

import pytest

from app.core.config import settings
from app.models import Cliente, Equipamento, EquipamentoCliente
from app.scripts.enviar_vencendo_growthhs import (
    agrupar_por_cliente,
    buscar_excluidos_por_os,
    buscar_vencendo,
    competencias_padrao,
    processar,
)

HOJE = date.today()
# Competencia de teste: o mes que vem inteiro esta SEMPRE no futuro em relacao a
# `date.today()`, entao o `max(hoje, primeiro dia do mes)` do filtro nunca corta nada
# e o teste nao muda de resultado conforme o dia em que roda.
MES_QUE_VEM = (HOJE.replace(day=1) + timedelta(days=32)).replace(day=1)
MES_SEGUINTE = (MES_QUE_VEM + timedelta(days=32)).replace(day=1)
ULTIMO_DIA_DO_MES_QUE_VEM = MES_SEGUINTE - timedelta(days=1)


# IDs explicitos e ACIMA de `CLIENTE_ESTOQUE_HS_ID` (2): com id auto-incrementado o
# segundo cliente caia justamente no 2 e era descartado pelo filtro de estoque interno,
# fazendo o teste de agrupamento falhar por um motivo que nao tem nada a ver com ele.
# A ordem 101 < 102 tambem e' a que o teste de agrupamento espera.
@pytest.fixture
def cliente(db_session):
    c = Cliente(id=101, nome="ACME Ltda")
    db_session.add(c); db_session.commit(); db_session.refresh(c)
    return c


@pytest.fixture
def outro_cliente(db_session):
    c = Cliente(id=102, nome="Beta SA")
    db_session.add(c); db_session.commit(); db_session.refresh(c)
    return c


@pytest.fixture
def equipamentos(db_session):
    """O conftest liga `PRAGMA foreign_keys=ON`, entao `equipamentos_cliente.equipamento`
    PRECISA apontar para uma linha real de `equipamentos` — inclusive os IDs de exclusao
    (Phoebus 36 / EBS 37), que sao criados aqui com ID explicito para os testes de filtro."""
    linhas = {
        "modulo": Equipamento(id=settings.EQUIPAMENTO_MODULO_ID, descricao="Modulo de calibracao"),
        "phoebus": Equipamento(id=settings.EQUIPAMENTO_PHOEBUS_ID, descricao="Phoebus"),
        "ebs": Equipamento(id=settings.EQUIPAMENTO_EBS_ID, descricao="EBS"),
    }
    db_session.add_all(linhas.values()); db_session.commit()
    return {nome: eq.id for nome, eq in linhas.items()}


def _ec(db_session, cliente_id, *, vence, equipamento=None, ativo=True, os_atual=None):
    ec = EquipamentoCliente(
        cliente=cliente_id,
        equipamento=equipamento if equipamento is not None else settings.EQUIPAMENTO_MODULO_ID,
        serie=f"SN-{vence.isoformat()}",
        prox_calibragem=vence, ativo=ativo, os_atual=os_atual,
    )
    db_session.add(ec); db_session.commit(); db_session.refresh(ec)
    return ec


def _ids(linhas):
    return {linha["ec"].id for linha in linhas}


def _dia(n):
    """Dia `n` do mes de teste."""
    return MES_QUE_VEM.replace(day=n)


# ---------------------------------------------------------------------------
# Selecao por competencia
# ---------------------------------------------------------------------------

def test_pega_dentro_da_competencia(db_session, cliente, equipamentos):
    dentro = _ec(db_session, cliente.id, vence=_dia(10))
    assert dentro.id in _ids(buscar_vencendo(db_session, MES_QUE_VEM))


def test_inclui_as_duas_bordas_do_mes(db_session, cliente, equipamentos):
    """Janela FECHADA nos dois lados: dia 1 entra, ultimo dia do mes entra."""
    primeiro = _ec(db_session, cliente.id, vence=_dia(1))
    ultimo = _ec(db_session, cliente.id, vence=ULTIMO_DIA_DO_MES_QUE_VEM)
    ids = _ids(buscar_vencendo(db_session, MES_QUE_VEM))
    assert primeiro.id in ids
    assert ultimo.id in ids


def test_ignora_o_mes_seguinte(db_session, cliente, equipamentos):
    """Cada competencia e' um card diferente; misturar meses quebraria a chave."""
    proximo = _ec(db_session, cliente.id, vence=MES_SEGUINTE)
    assert proximo.id not in _ids(buscar_vencendo(db_session, MES_QUE_VEM))


def test_ignora_vencidos(db_session, cliente, equipamentos):
    """Vencido e' backlog da Etapa 1 — incluir aqui geraria milhares de cards
    num formato diferente do que a Etapa 1 ja criou."""
    vencido = _ec(db_session, cliente.id, vence=HOJE - timedelta(days=1))
    assert vencido.id not in _ids(buscar_vencendo(db_session, HOJE.replace(day=1)))


def test_ignora_com_os_em_andamento(db_session, cliente, equipamentos):
    """Se o cliente ja mandou o aparelho, 'entre em contato' e' ruido."""
    em_os = _ec(db_session, cliente.id, vence=_dia(10), os_atual=12345)
    assert em_os.id not in _ids(buscar_vencendo(db_session, MES_QUE_VEM))


def test_ignora_inativo(db_session, cliente, equipamentos):
    inativo = _ec(db_session, cliente.id, vence=_dia(10), ativo=False)
    assert inativo.id not in _ids(buscar_vencendo(db_session, MES_QUE_VEM))


def test_ignora_phoebus_e_ebs(db_session, cliente, equipamentos):
    """Sao hospedeiros: nao sao calibrados, quem calibra e' o modulo dentro deles."""
    ph = _ec(db_session, cliente.id, vence=_dia(10),
             equipamento=settings.EQUIPAMENTO_PHOEBUS_ID)
    ebs = _ec(db_session, cliente.id, vence=_dia(11),
              equipamento=settings.EQUIPAMENTO_EBS_ID)
    ids = _ids(buscar_vencendo(db_session, MES_QUE_VEM))
    assert ph.id not in ids
    assert ebs.id not in ids


def test_ignora_cliente_de_estoque_interno(db_session, equipamentos):
    estoque = Cliente(id=settings.CLIENTE_ESTOQUE_HS_ID, nome="Estoque HS")
    db_session.add(estoque); db_session.commit()
    ec = _ec(db_session, settings.CLIENTE_ESTOQUE_HS_ID, vence=_dia(10))
    assert ec.id not in _ids(buscar_vencendo(db_session, MES_QUE_VEM))


# ---------------------------------------------------------------------------
# Agrupamento (puro)
# ---------------------------------------------------------------------------

def test_agrupa_por_cliente_e_ordena_por_vencimento(db_session, cliente, outro_cliente,
                                                    equipamentos):
    a2 = _ec(db_session, cliente.id, vence=_dia(20))
    a1 = _ec(db_session, cliente.id, vence=_dia(3))
    b1 = _ec(db_session, outro_cliente.id, vence=_dia(9))

    grupos = agrupar_por_cliente(buscar_vencendo(db_session, MES_QUE_VEM))

    assert [[l["ec"].id for l in g] for g in grupos] == [[a1.id, a2.id], [b1.id]]


def test_agrupar_lista_vazia():
    assert agrupar_por_cliente([]) == []


# ---------------------------------------------------------------------------
# Excluidos por OS — so entram no relatorio, nunca viram card
# ---------------------------------------------------------------------------

def test_excluidos_por_os_lista_quem_ficou_de_fora(db_session, cliente, equipamentos):
    em_os = _ec(db_session, cliente.id, vence=_dia(10), os_atual=10902)
    _ec(db_session, cliente.id, vence=_dia(11))
    excluidos = buscar_excluidos_por_os(db_session, MES_QUE_VEM)
    assert _ids(excluidos) == {em_os.id}


def test_excluidos_respeita_os_demais_filtros(db_session, cliente, equipamentos):
    inativo_em_os = _ec(db_session, cliente.id, vence=_dia(10), os_atual=1, ativo=False)
    assert inativo_em_os.id not in _ids(buscar_excluidos_por_os(db_session, MES_QUE_VEM))


# ---------------------------------------------------------------------------
# Competencias padrao
# ---------------------------------------------------------------------------

def test_competencias_padrao_sao_o_mes_corrente_e_o_seguinte():
    assert competencias_padrao(date(2026, 8, 14)) == [date(2026, 8, 1), date(2026, 9, 1)]


def test_competencias_padrao_viram_o_ano():
    assert competencias_padrao(date(2026, 12, 3)) == [date(2026, 12, 1), date(2027, 1, 1)]


# ---------------------------------------------------------------------------
# processar — best-effort POR CLIENTE
# ---------------------------------------------------------------------------

def _fake_envio(monkeypatch, resposta):
    enviados = []

    def enviar(card):
        enviados.append(card)
        return resposta(card) if callable(resposta) else resposta

    monkeypatch.setattr("app.scripts.enviar_vencendo_growthhs.enviar_card_sync", enviar)
    return enviados


def test_dry_run_nao_envia_mas_monta(db_session, cliente, equipamentos, monkeypatch):
    """A montagem acontece SEMPRE — e' assim que o dry-run valida o payload."""
    _ec(db_session, cliente.id, vence=_dia(10))
    enviados = _fake_envio(monkeypatch, {"created": True})
    r = processar(db_session, competencias=[MES_QUE_VEM], enviar=False)
    assert enviados == []
    assert r["clientes"] == 1
    assert r["aparelhos"] == 1
    assert r["criados"] == 0


def test_um_card_por_cliente_com_todos_os_aparelhos(db_session, cliente, outro_cliente,
                                                    equipamentos, monkeypatch):
    """O motivo da mudanca: 3 aparelhos do mesmo cliente = 1 card, nao 3."""
    for dia in (3, 10, 20):
        _ec(db_session, cliente.id, vence=_dia(dia))
    _ec(db_session, outro_cliente.id, vence=_dia(9))

    enviados = _fake_envio(monkeypatch, {"created": True})
    r = processar(db_session, competencias=[MES_QUE_VEM], enviar=True)

    assert len(enviados) == 2
    assert r["clientes"] == 2 and r["aparelhos"] == 4 and r["criados"] == 2
    por_chave = {c["external_id"]: c for c in enviados}
    assert len(por_chave[f"{cliente.id}:{MES_QUE_VEM:%Y-%m}"]["devices"]) == 3
    assert len(por_chave[f"{outro_cliente.id}:{MES_QUE_VEM:%Y-%m}"]["devices"]) == 1


def test_duas_competencias_geram_um_card_por_mes(db_session, cliente, equipamentos,
                                                 monkeypatch):
    """A rodada varre mes corrente + seguinte: o mesmo cliente ganha um card por mes,
    com chaves diferentes."""
    _ec(db_session, cliente.id, vence=_dia(10))
    _ec(db_session, cliente.id, vence=MES_SEGUINTE.replace(day=5))

    enviados = _fake_envio(monkeypatch, {"created": True})
    r = processar(db_session, competencias=[MES_QUE_VEM, MES_SEGUINTE], enviar=True)

    assert r["criados"] == 2
    assert {c["external_id"] for c in enviados} == {
        f"{cliente.id}:{MES_QUE_VEM:%Y-%m}",
        f"{cliente.id}:{MES_SEGUINTE:%Y-%m}",
    }


def test_competencia_ja_varrida_conta_como_existente(db_session, cliente, equipamentos,
                                                     monkeypatch):
    """`created: false` e' o mecanismo que faz a 2a rodada em diante subir so o mes
    novo da ponta — nao pode ser contado como criado nem como falha."""
    _ec(db_session, cliente.id, vence=_dia(10))
    _fake_envio(monkeypatch, {"created": False})
    r = processar(db_session, competencias=[MES_QUE_VEM], enviar=True)
    assert r["criados"] == 0
    assert r["existentes"] == 1
    assert r["falhas"] == 0


def test_falha_num_cliente_nao_aborta_os_outros(db_session, cliente, outro_cliente,
                                                equipamentos, monkeypatch):
    """Best-effort POR CLIENTE: um 422 num card nao pode derrubar a rodada."""
    _ec(db_session, cliente.id, vence=_dia(3))
    _ec(db_session, cliente.id, vence=_dia(4))
    _ec(db_session, outro_cliente.id, vence=_dia(9))

    def falha_no_primeiro(card):
        if card["external_id"].startswith(f"{cliente.id}:"):
            raise RuntimeError("GrowthHS respondeu 422: campo invalido")
        return {"created": True}

    _fake_envio(monkeypatch, falha_no_primeiro)
    r = processar(db_session, competencias=[MES_QUE_VEM], enviar=True)

    assert r["criados"] == 1
    assert r["falhas"] == 1                      # falha conta CLIENTE
    assert len(r["pendencias"]) == 2             # pendencia lista APARELHO
    assert all(p["tipo"] == "falha" for p in r["pendencias"])
    assert all("422" in p["motivo"] for p in r["pendencias"])
    assert {p["cliente_id"] for p in r["pendencias"]} == {cliente.id}


def test_excluidos_por_os_entram_no_relatorio_sem_virar_falha(db_session, cliente,
                                                              equipamentos, monkeypatch):
    em_os = _ec(db_session, cliente.id, vence=_dia(10), os_atual=10902)
    _ec(db_session, cliente.id, vence=_dia(11))
    _fake_envio(monkeypatch, {"created": True})

    r = processar(db_session, competencias=[MES_QUE_VEM], enviar=True)

    assert r["falhas"] == 0
    assert len(r["excluidos"]) == 1
    linha = r["excluidos"][0]
    assert linha["tipo"] == "excluido"
    assert linha["equipamento_cliente_id"] == em_os.id
    assert "10902" in linha["motivo"]
    assert linha["competencia"] == f"{MES_QUE_VEM:%Y-%m}"


def test_limite_corta_por_cliente(db_session, cliente, outro_cliente, equipamentos,
                                  monkeypatch):
    _ec(db_session, cliente.id, vence=_dia(3))
    _ec(db_session, cliente.id, vence=_dia(4))
    _ec(db_session, outro_cliente.id, vence=_dia(9))
    _fake_envio(monkeypatch, {"created": True})

    r = processar(db_session, competencias=[MES_QUE_VEM], enviar=True, limite=1)

    assert r["clientes"] == 1
    assert r["aparelhos"] == 2       # o limite corta CLIENTES, nao aparelhos
    assert r["criados"] == 1


# ---------------------------------------------------------------------------
# main() — a COSTURA entre o argparse e o processar()
#
# `test_limite_corta_por_cliente` chama processar() direto e sempre passou, mas o
# main() esquecia de repassar `limite=args.limite`: quem rodasse `--limite 5` para um
# teste controlado enviaria a rodada INTEIRA (409 cards em 20/07/2026),
# irreversivelmente. Os testes daqui exercitam main() de ponta a ponta.
# ---------------------------------------------------------------------------

def _rodar_main(monkeypatch, tmp_path, argv, db_session):
    import app.scripts.enviar_vencendo_growthhs as mod

    recebido = {}
    real_processar = mod.processar

    def espiao(db, **kw):
        recebido.update(kw)
        return real_processar(db_session, **kw)

    monkeypatch.setattr(mod, "processar", espiao)
    monkeypatch.setattr(mod, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)
    monkeypatch.setattr(mod, "integracao_ativa", lambda: True)
    monkeypatch.setattr(mod, "enviar_card_sync", lambda card: {"created": True})
    monkeypatch.setattr(sys, "argv", ["enviar_vencendo_growthhs",
                                      "--pendencias", str(tmp_path / "p.csv"), *argv])
    mod.main()
    return recebido


def test_main_repassa_o_limite(db_session, cliente, equipamentos, monkeypatch, tmp_path):
    _ec(db_session, cliente.id, vence=_dia(10))
    recebido = _rodar_main(monkeypatch, tmp_path, ["--dry-run", "--limite", "2"], db_session)
    assert recebido["limite"] == 2


def test_main_repassa_competencias_e_dry_run(db_session, cliente, equipamentos,
                                             monkeypatch, tmp_path):
    _ec(db_session, cliente.id, vence=_dia(10))
    recebido = _rodar_main(
        monkeypatch, tmp_path,
        ["--dry-run", "--competencia", "2026-08", "--competencia", "2026-09"], db_session)
    assert recebido["competencias"] == [date(2026, 8, 1), date(2026, 9, 1)]
    assert recebido["enviar"] is False


def test_main_sem_competencia_usa_mes_corrente_e_seguinte(db_session, cliente,
                                                          equipamentos, monkeypatch,
                                                          tmp_path):
    _ec(db_session, cliente.id, vence=_dia(10))
    recebido = _rodar_main(monkeypatch, tmp_path, ["--dry-run"], db_session)
    assert recebido["competencias"] == competencias_padrao(date.today())


def test_main_recusa_competencia_malformada(db_session, monkeypatch, tmp_path):
    """Erro de digitacao tem que morrer no argparse, nao virar uma rodada vazia
    silenciosa."""
    import app.scripts.enviar_vencendo_growthhs as mod
    monkeypatch.setattr(mod, "integracao_ativa", lambda: True)
    monkeypatch.setattr(sys, "argv", ["enviar_vencendo_growthhs", "--dry-run",
                                      "--pendencias", str(tmp_path / "p.csv"),
                                      "--competencia", "agosto"])
    with pytest.raises(SystemExit) as saida:
        mod.main()
    assert saida.value.code == 2      # argparse


def test_main_envia_por_padrao_sem_dry_run(db_session, cliente, equipamentos,
                                           monkeypatch, tmp_path):
    """O default deste script e' ENVIAR — o inverso do de atrasados, de proposito."""
    _ec(db_session, cliente.id, vence=_dia(10))
    recebido = _rodar_main(monkeypatch, tmp_path, [], db_session)
    assert recebido["enviar"] is True
    assert recebido["limite"] is None


def test_main_imprime_falhas_no_stdout(db_session, cliente, equipamentos,
                                       monkeypatch, tmp_path, capsys):
    """Em producao a imagem sobe pelo Dockerfile sem bind mount, entao o CSV pode ser
    efemero. O stdout vai para o log do servico e e' o unico canal que sobrevive
    sempre — se as falhas sairem so no CSV, o job fica cego quando algo quebra."""
    import app.scripts.enviar_vencendo_growthhs as mod
    ec = _ec(db_session, cliente.id, vence=_dia(10))

    def sempre_falha(card):
        raise RuntimeError("GrowthHS respondeu 422: campo invalido")

    monkeypatch.setattr(mod, "enviar_card_sync", sempre_falha)
    monkeypatch.setattr(mod, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)
    monkeypatch.setattr(mod, "integracao_ativa", lambda: True)
    monkeypatch.setattr(sys, "argv", ["enviar_vencendo_growthhs",
                                      "--pendencias", str(tmp_path / "p.csv")])

    with pytest.raises(SystemExit) as saida:
        mod.main()

    assert saida.value.code == 1          # o operador precisa conseguir alertar
    impresso = capsys.readouterr().out
    assert f"aparelho={ec.id}" in impresso
    assert "422" in impresso


def test_main_grava_falhas_e_excluidos_no_mesmo_csv(db_session, cliente, equipamentos,
                                                    monkeypatch, tmp_path):
    import csv as csv_mod

    import app.scripts.enviar_vencendo_growthhs as mod
    _ec(db_session, cliente.id, vence=_dia(10), os_atual=10902)
    _ec(db_session, cliente.id, vence=_dia(11))

    caminho = tmp_path / "p.csv"
    monkeypatch.setattr(mod, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)
    monkeypatch.setattr(mod, "integracao_ativa", lambda: True)
    monkeypatch.setattr(mod, "enviar_card_sync", lambda card: {"created": True})
    monkeypatch.setattr(sys, "argv", ["enviar_vencendo_growthhs",
                                      "--pendencias", str(caminho),
                                      "--competencia", f"{MES_QUE_VEM:%Y-%m}"])
    mod.main()      # sem falha => sem SystemExit

    with open(caminho, encoding="utf-8") as f:
        linhas = list(csv_mod.DictReader(f))
    assert [l["tipo"] for l in linhas] == ["excluido"]
    assert linhas[0]["competencia"] == f"{MES_QUE_VEM:%Y-%m}"
