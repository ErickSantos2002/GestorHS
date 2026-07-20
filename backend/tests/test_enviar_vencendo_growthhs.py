import sys
from datetime import date, timedelta

import pytest

from app.core.config import settings
from app.models import Cliente, Equipamento, EquipamentoCliente
from app.scripts.enviar_vencendo_growthhs import buscar_vencendo, processar

HOJE = date.today()


@pytest.fixture
def cliente(db_session):
    c = Cliente(nome="ACME Ltda")
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


def _ec(db_session, cliente_id, *, dias, equipamento=None, ativo=True, os_atual=None):
    ec = EquipamentoCliente(
        cliente=cliente_id,
        equipamento=equipamento if equipamento is not None else settings.EQUIPAMENTO_MODULO_ID,
        serie=f"SN-{dias}",
        prox_calibragem=HOJE + timedelta(days=dias), ativo=ativo, os_atual=os_atual,
    )
    db_session.add(ec); db_session.commit(); db_session.refresh(ec)
    return ec


def _ids(linhas):
    return {linha["ec"].id for linha in linhas}


def test_pega_dentro_da_janela(db_session, cliente, equipamentos):
    dentro = _ec(db_session, cliente.id, dias=10)
    assert dentro.id in _ids(buscar_vencendo(db_session, 50))


def test_inclui_as_duas_bordas(db_session, cliente, equipamentos):
    """Janela FECHADA nos dois lados: vence hoje entra, vence no ultimo dia entra."""
    hoje_mesmo = _ec(db_session, cliente.id, dias=0)
    ultimo = _ec(db_session, cliente.id, dias=50)
    ids = _ids(buscar_vencendo(db_session, 50))
    assert hoje_mesmo.id in ids
    assert ultimo.id in ids


def test_ignora_vencidos(db_session, cliente, equipamentos):
    """Vencido e' backlog da Etapa 1 — incluir aqui geraria milhares de cards
    num formato diferente do que a Etapa 1 ja criou."""
    vencido = _ec(db_session, cliente.id, dias=-1)
    assert vencido.id not in _ids(buscar_vencendo(db_session, 50))


def test_ignora_fora_da_janela(db_session, cliente, equipamentos):
    longe = _ec(db_session, cliente.id, dias=51)
    assert longe.id not in _ids(buscar_vencendo(db_session, 50))


def test_ignora_com_os_em_andamento(db_session, cliente, equipamentos):
    """Se o cliente ja mandou o aparelho, 'entre em contato' e' ruido."""
    em_os = _ec(db_session, cliente.id, dias=10, os_atual=12345)
    assert em_os.id not in _ids(buscar_vencendo(db_session, 50))


def test_ignora_inativo(db_session, cliente, equipamentos):
    inativo = _ec(db_session, cliente.id, dias=10, ativo=False)
    assert inativo.id not in _ids(buscar_vencendo(db_session, 50))


def test_ignora_phoebus_e_ebs(db_session, cliente, equipamentos):
    """Sao hospedeiros: nao sao calibrados, quem calibra e' o modulo dentro deles."""
    ph = _ec(db_session, cliente.id, dias=10, equipamento=settings.EQUIPAMENTO_PHOEBUS_ID)
    ebs = _ec(db_session, cliente.id, dias=11, equipamento=settings.EQUIPAMENTO_EBS_ID)
    ids = _ids(buscar_vencendo(db_session, 50))
    assert ph.id not in ids
    assert ebs.id not in ids


def test_ignora_cliente_de_estoque_interno(db_session, equipamentos):
    estoque = Cliente(id=settings.CLIENTE_ESTOQUE_HS_ID, nome="Estoque HS")
    db_session.add(estoque); db_session.commit()
    ec = _ec(db_session, settings.CLIENTE_ESTOQUE_HS_ID, dias=10)
    assert ec.id not in _ids(buscar_vencendo(db_session, 50))


def test_dias_menor_encolhe_a_janela(db_session, cliente, equipamentos):
    perto = _ec(db_session, cliente.id, dias=5)
    longe = _ec(db_session, cliente.id, dias=40)
    ids = _ids(buscar_vencendo(db_session, 7))
    assert perto.id in ids
    assert longe.id not in ids


def test_dry_run_nao_envia_mas_monta(db_session, cliente, equipamentos, monkeypatch):
    """A montagem acontece SEMPRE — e' assim que o dry-run valida o payload."""
    _ec(db_session, cliente.id, dias=10)
    chamadas = []
    monkeypatch.setattr("app.scripts.enviar_vencendo_growthhs.enviar_card_sync",
                        lambda card: chamadas.append(card) or {"created": True})
    r = processar(db_session, dias=50, enviar=False)
    assert chamadas == []
    assert r["candidatos"] == 1
    assert r["criados"] == 0


def test_envia_e_conta_criados_e_existentes(db_session, cliente, equipamentos, monkeypatch):
    _ec(db_session, cliente.id, dias=10)
    _ec(db_session, cliente.id, dias=11)
    respostas = [{"created": True}, {"created": False}]
    monkeypatch.setattr("app.scripts.enviar_vencendo_growthhs.enviar_card_sync",
                        lambda card: respostas.pop(0))
    r = processar(db_session, dias=50, enviar=True)
    assert r["criados"] == 1
    assert r["existentes"] == 1
    assert r["falhas"] == 0


def test_falha_num_aparelho_nao_aborta_os_outros(db_session, cliente, equipamentos, monkeypatch):
    """Best-effort POR APARELHO: um 422 num card nao pode derrubar a rodada."""
    _ec(db_session, cliente.id, dias=10)
    _ec(db_session, cliente.id, dias=11)
    _ec(db_session, cliente.id, dias=12)

    def falha_no_segundo(card):
        falha_no_segundo.n += 1
        if falha_no_segundo.n == 2:
            raise RuntimeError("GrowthHS respondeu 422: campo invalido")
        return {"created": True}
    falha_no_segundo.n = 0

    monkeypatch.setattr("app.scripts.enviar_vencendo_growthhs.enviar_card_sync",
                        falha_no_segundo)
    r = processar(db_session, dias=50, enviar=True)
    assert r["criados"] == 2
    assert r["falhas"] == 1
    assert len(r["pendencias"]) == 1
    assert "422" in r["pendencias"][0]["motivo"]


def test_limite_corta_a_rodada(db_session, cliente, equipamentos, monkeypatch):
    for d in (10, 11, 12):
        _ec(db_session, cliente.id, dias=d)
    monkeypatch.setattr("app.scripts.enviar_vencendo_growthhs.enviar_card_sync",
                        lambda card: {"created": True})
    r = processar(db_session, dias=50, enviar=True, limite=2)
    assert r["candidatos"] == 2
    assert r["criados"] == 2


# ---------------------------------------------------------------------------
# main() — a COSTURA entre o argparse e o processar()
#
# `test_limite_corta_a_rodada` chama processar() direto e sempre passou, mas o
# main() esquecia de repassar `limite=args.limite`: quem rodasse `--limite 5`
# para um teste controlado enviaria a rodada INTEIRA (409 cards em 20/07/2026),
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
    for d in (10, 11, 12):
        _ec(db_session, cliente.id, dias=d)
    recebido = _rodar_main(monkeypatch, tmp_path, ["--dry-run", "--limite", "2"], db_session)
    assert recebido["limite"] == 2


def test_main_repassa_dias_e_dry_run(db_session, cliente, equipamentos, monkeypatch, tmp_path):
    _ec(db_session, cliente.id, dias=10)
    recebido = _rodar_main(monkeypatch, tmp_path, ["--dry-run", "--dias", "7"], db_session)
    assert recebido["dias"] == 7
    assert recebido["enviar"] is False


def test_main_envia_por_padrao_sem_dry_run(db_session, cliente, equipamentos, monkeypatch, tmp_path):
    """O default deste script e' ENVIAR — o inverso do de atrasados, de proposito."""
    _ec(db_session, cliente.id, dias=10)
    recebido = _rodar_main(monkeypatch, tmp_path, [], db_session)
    assert recebido["enviar"] is True
    assert recebido["limite"] is None
