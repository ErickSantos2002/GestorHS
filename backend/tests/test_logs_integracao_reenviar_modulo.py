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


def _log(db, external_id):
    from app.models import LogIntegracao
    row = LogIntegracao(integracao="growthhs", tipo="os_card", external_id=external_id,
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
