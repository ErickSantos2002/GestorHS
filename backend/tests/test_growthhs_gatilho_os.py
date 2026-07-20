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


def _equip_modulo_com_elo(db_session, os_base):
    """Cria um Phoebus e um Modulo de calibracao instalado nele (elo aberto).

    Devolve (phoebus_ec, modulo_ec), ambos linhas de verdade de
    `equipamentos_cliente` — para exercitar `buscar_elo`/`montar_device` de
    ponta a ponta, sem nenhum mock no caminho de dados."""
    from datetime import date as _date
    from app.core.config import settings
    from app.models import Equipamento, EquipamentoCliente, InstalacaoModulo
    if db_session.get(Equipamento, settings.EQUIPAMENTO_MODULO_ID) is None:
        db_session.add(Equipamento(id=settings.EQUIPAMENTO_MODULO_ID, descricao="Modulo de Calibracao"))
        db_session.commit()
    pho = EquipamentoCliente(cliente=os_base["cliente"], equipamento=os_base["equipamento"], serie="WATFR01-00340")
    db_session.add(pho); db_session.commit(); db_session.refresh(pho)
    mod = EquipamentoCliente(cliente=os_base["cliente"], equipamento=settings.EQUIPAMENTO_MODULO_ID, serie="F005065")
    db_session.add(mod); db_session.commit(); db_session.refresh(mod)
    db_session.add(InstalacaoModulo(modulo=mod.id, phoebus=pho.id, entrou_em=_date(2026, 7, 18), origem="teste"))
    db_session.commit()
    return pho, mod


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


def test_agendar_card_os_caminho_feliz_chega_no_add_task_com_payload_real(
    client, usuario_comum, usuario_lab, fases_seed, os_base, db_session, monkeypatch,
):
    """Fix 2: todo outro teste deste arquivo ou espiona `agendar_card_os` (sem olhar
    o payload que ele monta), ou desliga a integracao, ou forca excecao na montagem.
    Nenhum confirma que um payload bem formado chega em
    `add_task(hsgrowth_client.enviar_card, card)` a partir de linhas ORM de
    verdade — uma regressao em `ordem.equipamento_rel`, na ordem dos argumentos
    de `montar_device` ou no alvo do `add_task` passaria a suite inteira sem
    ser notada.

    Monta a OS com modulo + elo (Phoebus) de verdade, o que tambem trava o
    Fix 1 (titulo com o aparelho do elo) de ponta a ponta."""
    from app.core.config import settings
    from app.integrations import hsgrowth_client
    monkeypatch.setattr(settings, "HSGROWTH_BASE_URL", "https://growth.test")
    monkeypatch.setattr(settings, "HSGROWTH_API_KEY", "chave-123")

    pho, mod = _equip_modulo_com_elo(db_session, os_base)

    capturados = []
    from fastapi import BackgroundTasks
    original_add_task = BackgroundTasks.add_task

    def _add_task_espiao(self, func, *a, **k):
        if func is hsgrowth_client.enviar_card:
            capturados.append(a[0] if a else k.get("card"))
        return original_add_task(self, func, *a, **k)
    monkeypatch.setattr(BackgroundTasks, "add_task", _add_task_espiao)

    he = _headers(client, "comum@hs.com", "senha123")
    hl = _headers(client, "lab@hs.com", "senha123")
    oid = _abrir(client, he, mod.id)["id"]
    client.post(f"/ordens/{oid}/avancar", json={}, headers=he)  # 4 -> 5

    db_session.add(CertificadoModelo(equipamento=settings.EQUIPAMENTO_MODULO_ID, tipo="C", texto="<p>[serie]</p>"))
    db_session.commit()
    client.post(f"/ordens/{oid}/gerar-certificado", json={"calib_cert": "C-1"}, headers=hl)

    r = client.post(f"/ordens/{oid}/avancar", json={"prox_calibragem": "2027-06-09"}, headers=hl)  # 5 -> 6
    assert r.status_code == 200 and r.json()["fase"] == 6

    assert len(capturados) == 1
    card = capturados[0]
    assert card["source"] == "gestorhs.os"
    assert card["external_id"] == str(oid)
    assert card["devices"][0]["serial_number"] == "WATFR01-00340"
    # Fix 1 de ponta a ponta: titulo com o Phoebus, nao o numero do modulo.
    assert "WATFR01-00340" in card["title"]
    assert "F005065" not in card["title"]


def test_agendar_card_os_sem_equipamento_nao_agenda_e_loga_warning_sem_stacktrace(db_session, monkeypatch, caplog):
    """Fix 4: `ordem.equipamento_cliente` e' nullable — uma OS sem equipamento e' um
    dado benigno, nao uma excecao. Antes caia no `except` generico e virava log de
    erro com stack trace; agora e' guardado explicitamente (warning, sem card)."""
    import logging
    from types import SimpleNamespace
    from app.core.config import settings
    from app.api.growthhs_cards import agendar_card_os
    monkeypatch.setattr(settings, "HSGROWTH_BASE_URL", "https://growth.test")
    monkeypatch.setattr(settings, "HSGROWTH_API_KEY", "chave-123")

    ordem = SimpleNamespace(id=777, equipamento_rel=None, equipamento_descricao=None)

    class _BackgroundTasksFake:
        def __init__(self):
            self.chamadas = []

        def add_task(self, func, *a, **k):
            self.chamadas.append((func, a, k))

    bt = _BackgroundTasksFake()
    with caplog.at_level(logging.WARNING, logger="app.api.growthhs_cards"):
        agendar_card_os(db_session, bt, ordem)

    assert bt.chamadas == []
    assert any(r.levelno == logging.WARNING and "777" in r.getMessage() for r in caplog.records)
    assert not any(r.levelno >= logging.ERROR for r in caplog.records)


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
