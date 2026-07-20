"""Gatilho do card GrowthHS ao sair do laboratorio (5->6), disparado por `avancar`.

Mesmo padrao de `test_ordens_avancar.py`: cria a OS via API e avanca pelas fases,
monkeypatchando `agendar_card_os` (contagem de chamadas) ou `background_tasks.add_task`
(pra confirmar que nada e' agendado com a integracao desligada).
"""
from app.models import CertificadoModelo, Ordem


def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _abrir(client, h, equipamento_cliente):
    cid = client.post("/caixas", json={"obs": "lote"}, headers=h).json()["id"]
    return client.post(
        "/ordens",
        json={"equipamento_cliente": equipamento_cliente, "tipo_servico": "C", "caixa": cid},
        headers=h,
    ).json()


def _gerar_certificado(client, hl, db_session, os_base, oid):
    db_session.add(CertificadoModelo(equipamento=os_base["equipamento"], tipo="C", texto="<p>[serie]</p>"))
    db_session.commit()
    client.post(f"/ordens/{oid}/gerar-certificado", json={"calib_cert": "C-1"}, headers=hl)


def _spy_gatilho(monkeypatch):
    chamadas = []
    import app.api.ordens as ordens_mod
    monkeypatch.setattr(ordens_mod, "agendar_card_os", lambda db, bt, ordem: chamadas.append(ordem.id))
    return chamadas


def test_avancar_5_para_6_chama_o_gatilho_uma_vez(client, usuario_comum, usuario_lab, fases_seed, os_base, db_session, monkeypatch):
    chamadas = _spy_gatilho(monkeypatch)
    he = _headers(client, "comum@hs.com", "senha123")
    hl = _headers(client, "lab@hs.com", "senha123")
    oid = _abrir(client, he, os_base["equipamento_cliente"])["id"]
    client.post(f"/ordens/{oid}/avancar", json={}, headers=he)  # 4 -> 5
    _gerar_certificado(client, hl, db_session, os_base, oid)
    r = client.post(f"/ordens/{oid}/avancar", json={"prox_calibragem": "2027-06-09"}, headers=hl)  # 5 -> 6
    assert r.status_code == 200 and r.json()["fase"] == 6
    assert chamadas == [oid]


def test_avancar_4_para_5_nao_chama(client, usuario_comum, fases_seed, os_base, monkeypatch):
    chamadas = _spy_gatilho(monkeypatch)
    he = _headers(client, "comum@hs.com", "senha123")
    oid = _abrir(client, he, os_base["equipamento_cliente"])["id"]
    r = client.post(f"/ordens/{oid}/avancar", json={}, headers=he)  # 4 -> 5
    assert r.status_code == 200 and r.json()["fase"] == 5
    assert chamadas == []


def test_avancar_6_para_10_nao_chama(client, usuario_comercial, fases_seed, os_base, db_session, monkeypatch):
    chamadas = _spy_gatilho(monkeypatch)
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"], fase=6, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    hc = _headers(client, "comercial@hs.com", "senha123")
    r = client.post(f"/ordens/{o.id}/avancar", json={}, headers=hc)  # 6 -> 10
    assert r.status_code == 200 and r.json()["fase"] == 10
    assert chamadas == []


def test_avancar_10_para_7_nao_chama(client, usuario_financeiro, fases_seed, os_base, db_session, monkeypatch):
    chamadas = _spy_gatilho(monkeypatch)
    o = Ordem(
        cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"], fase=10, situacao="E",
        nota_fiscal="nf.pdf", nota_fiscal_numero="1",
    )
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    hf = _headers(client, "fin@hs.com", "senha123")
    r = client.post(f"/ordens/{o.id}/avancar", json={}, headers=hf)  # 10 -> 7
    assert r.status_code == 200 and r.json()["fase"] == 7
    assert chamadas == []


def test_avancar_7_para_8_nao_chama(client, usuario_comum, fases_seed, os_base, db_session, monkeypatch):
    chamadas = _spy_gatilho(monkeypatch)
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"], fase=7, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    he = _headers(client, "comum@hs.com", "senha123")
    r = client.post(f"/ordens/{o.id}/avancar", json={"cod_retorno": "BR123"}, headers=he)  # 7 -> 8
    assert r.status_code == 200 and r.json()["fase"] == 8
    assert chamadas == []


def test_cancelar_nao_chama(client, usuario_comum, fases_seed, os_base, monkeypatch):
    chamadas = _spy_gatilho(monkeypatch)
    he = _headers(client, "comum@hs.com", "senha123")
    oid = _abrir(client, he, os_base["equipamento_cliente"])["id"]
    r = client.post(f"/ordens/{oid}/cancelar", json={"motivo": "teste"}, headers=he)
    assert r.status_code == 200 and r.json()["fase"] == 9
    assert chamadas == []


def test_integracao_desligada_nao_agenda_nada(client, usuario_comum, usuario_lab, fases_seed, os_base, db_session, monkeypatch):
    """Com HSGROWTH desligado, nenhum `add_task` do card do GrowthHS e' agendado.

    Filtra pelo alvo `hsgrowth_client.enviar_card` especificamente: o TaskHS
    (`_agendar_espelhamento`) tambem agenda tasks a cada avanco de fase, e essa
    integracao e' independente da do GrowthHS — nao pode gerar falso positivo
    aqui."""
    from app.core.config import settings
    from app.integrations import hsgrowth_client
    monkeypatch.setattr(settings, "HSGROWTH_BASE_URL", "")
    monkeypatch.setattr(settings, "HSGROWTH_API_KEY", "")

    chamadas_growthhs = []
    from fastapi import BackgroundTasks
    original_add_task = BackgroundTasks.add_task

    def _add_task_espiao(self, func, *a, **k):
        if func is hsgrowth_client.enviar_card:
            chamadas_growthhs.append((a, k))
        return original_add_task(self, func, *a, **k)
    monkeypatch.setattr(BackgroundTasks, "add_task", _add_task_espiao)

    he = _headers(client, "comum@hs.com", "senha123")
    hl = _headers(client, "lab@hs.com", "senha123")
    oid = _abrir(client, he, os_base["equipamento_cliente"])["id"]
    client.post(f"/ordens/{oid}/avancar", json={}, headers=he)  # 4 -> 5
    _gerar_certificado(client, hl, db_session, os_base, oid)
    r = client.post(f"/ordens/{oid}/avancar", json={"prox_calibragem": "2027-06-09"}, headers=hl)  # 5 -> 6
    assert r.status_code == 200 and r.json()["fase"] == 6
    assert chamadas_growthhs == []


def test_gatilho_levanta_excecao_mas_os_avanca_mesmo_assim(client, usuario_comum, usuario_lab, fases_seed, os_base, db_session, monkeypatch):
    """Integracao LIGADA e a montagem do payload explode (dado ruim, relacionamento
    faltando, o que for) — o try/except dentro de `agendar_card_os` precisa
    engolir isso: o `avancar` nao pode propagar o erro pro chamador."""
    import app.api.growthhs_cards as cards_mod
    from app.core.config import settings
    monkeypatch.setattr(settings, "HSGROWTH_BASE_URL", "https://growth.test")
    monkeypatch.setattr(settings, "HSGROWTH_API_KEY", "chave-123")

    def _explode(*a, **k):
        raise RuntimeError("boom na montagem")
    monkeypatch.setattr(cards_mod, "montar_card_os", _explode)

    he = _headers(client, "comum@hs.com", "senha123")
    hl = _headers(client, "lab@hs.com", "senha123")
    oid = _abrir(client, he, os_base["equipamento_cliente"])["id"]
    client.post(f"/ordens/{oid}/avancar", json={}, headers=he)  # 4 -> 5
    _gerar_certificado(client, hl, db_session, os_base, oid)
    r = client.post(f"/ordens/{oid}/avancar", json={"prox_calibragem": "2027-06-09"}, headers=hl)  # 5 -> 6
    assert r.status_code == 200
    assert r.json()["fase"] == 6
