"""Reenvio de log de integracao recusa payloads que apontam para OS/caixa de
modulo/phoebus -- o mesmo botao 'Reenviar' da tela de logs nao pode ressuscitar
um card que a equipe arquivou a mao (achado B do review final de
feat/caixa-modulo-sem-integracao)."""
from app.core.config import settings


def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _cliente_e_equipamentos(db):
    from app.models import Cliente, Equipamento
    cli = Cliente(nome="Cliente Reenvio", cgc="11222333000144")
    eq_comum = Equipamento(id=1, descricao="Eq comum")
    eq_modulo = Equipamento(id=settings.EQUIPAMENTO_MODULO_ID, descricao="Modulo")
    db.add_all([cli, eq_comum, eq_modulo])
    db.flush()
    return cli


def _ordem(db, cliente_id, catalogo, fase=6):
    from app.models import EquipamentoCliente, Ordem
    ec = EquipamentoCliente(cliente=cliente_id, equipamento=catalogo, serie=f"S{catalogo}")
    db.add(ec); db.flush()
    o = Ordem(cliente=cliente_id, equipamento_cliente=ec.id, fase=fase, situacao="E",
              desfecho_lab="liberado")
    db.add(o); db.commit(); db.refresh(o)
    return o


def _caixa(db, ordens):
    from app.models import Caixa
    cx = Caixa(obs="Caixa reenvio", fase=6)
    db.add(cx); db.flush()
    for o in ordens:
        o.caixa = cx.id
    db.commit(); db.refresh(cx)
    return cx


def _log(db, external_id, integracao="growthhs"):
    from app.models import LogIntegracao
    row = LogIntegracao(integracao=integracao, tipo="os_card", external_id=external_id,
                        status="erro", payload={"source": "gestorhs.os", "external_id": external_id})
    db.add(row); db.commit(); db.refresh(row)
    return row


def test_reenvio_de_os_de_modulo_e_recusado(client, usuario_admin, db_session, fases_seed, monkeypatch):
    from app.api import logs_integracao
    cli = _cliente_e_equipamentos(db_session)
    ordem = _ordem(db_session, cli.id, settings.EQUIPAMENTO_MODULO_ID)
    row = _log(db_session, str(ordem.id))
    chamadas = []
    monkeypatch.setattr(logs_integracao.hsgrowth_client, "enviar_card_sync",
                        lambda payload: chamadas.append(payload))
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.post(f"/logs-integracao/{row.id}/reenviar", headers=h)
    assert r.status_code == 409
    assert chamadas == []


def test_reenvio_de_caixa_de_modulo_e_recusado(client, usuario_admin, db_session, fases_seed, monkeypatch):
    from app.api import logs_integracao
    cli = _cliente_e_equipamentos(db_session)
    ordem = _ordem(db_session, cli.id, settings.EQUIPAMENTO_MODULO_ID)
    cx = _caixa(db_session, [ordem])
    row = _log(db_session, str(cx.id))
    chamadas = []
    monkeypatch.setattr(logs_integracao.hsgrowth_client, "enviar_card_sync",
                        lambda payload: chamadas.append(payload))
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.post(f"/logs-integracao/{row.id}/reenviar", headers=h)
    assert r.status_code == 409
    assert chamadas == []


def test_reenvio_de_os_comum_continua_funcionando(client, usuario_admin, db_session, fases_seed, monkeypatch):
    """Controle positivo: sem ele, os dois testes acima passariam mesmo com o
    endpoint quebrado (ex.: recusando tudo)."""
    from app.api import logs_integracao
    cli = _cliente_e_equipamentos(db_session)
    ordem = _ordem(db_session, cli.id, 1)
    row = _log(db_session, str(ordem.id))
    chamadas = []
    monkeypatch.setattr(logs_integracao.hsgrowth_client, "enviar_card_sync",
                        lambda payload: chamadas.append(payload))
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.post(f"/logs-integracao/{row.id}/reenviar", headers=h)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert len(chamadas) == 1


def test_reenvio_com_external_id_inexistente_continua_reenviando(client, usuario_admin, db_session, monkeypatch):
    from app.api import logs_integracao
    row = _log(db_session, "999999")
    chamadas = []
    monkeypatch.setattr(logs_integracao.hsgrowth_client, "enviar_card_sync",
                        lambda payload: chamadas.append(payload))
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.post(f"/logs-integracao/{row.id}/reenviar", headers=h)
    assert r.status_code == 200
    assert len(chamadas) == 1


def test_reenvio_de_caixa_com_phoebus_e_permitido_no_taskhs_mas_nao_no_growthhs(
        client, usuario_admin, db_session, fases_seed, monkeypatch):
    """Desde o inbound do TaskHS (18/09/2026), caixa com Phoebus virou card
    LEGITIMO no board do TaskHS -- e' o elo de que o avanco 6->10 depende. O
    "Reenviar" tinha ficado desatualizado (recusava com o criterio largo das
    DUAS integracoes) e barrava exatamente o card que a feature precisa poder
    reparar. No GrowthHS a caixa continua recusada: aquele board e' comercial e
    Phoebus nao tem proposta la."""
    from app.api import logs_integracao
    cli = _cliente_e_equipamentos(db_session)
    from app.models import Equipamento
    db_session.add(Equipamento(id=settings.EQUIPAMENTO_PHOEBUS_ID, descricao="Phoebus"))
    db_session.flush()
    ordem = _ordem(db_session, cli.id, settings.EQUIPAMENTO_PHOEBUS_ID)
    cx = _caixa(db_session, [ordem])

    row_taskhs = _log(db_session, str(cx.id), integracao="taskhs")
    chamadas_taskhs = []
    monkeypatch.setattr(logs_integracao.taskhs_client, "enviar_card_sync",
                        lambda payload: chamadas_taskhs.append(payload))
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.post(f"/logs-integracao/{row_taskhs.id}/reenviar", headers=h)
    assert r.status_code == 200
    assert len(chamadas_taskhs) == 1

    row_growthhs = _log(db_session, str(cx.id), integracao="growthhs")
    chamadas_growthhs = []
    monkeypatch.setattr(logs_integracao.hsgrowth_client, "enviar_card_sync",
                        lambda payload: chamadas_growthhs.append(payload))
    r = client.post(f"/logs-integracao/{row_growthhs.id}/reenviar", headers=h)
    assert r.status_code == 409
    assert chamadas_growthhs == []
