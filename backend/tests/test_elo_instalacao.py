import pytest
from datetime import date


def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _equip(db_session, os_base, serie, equipamento=None):
    """Cria um equipamento_cliente extra (serve como Phoebus ou Modulo)."""
    from app.models import EquipamentoCliente
    ec = EquipamentoCliente(
        cliente=os_base["cliente"],
        equipamento=equipamento if equipamento is not None else os_base["equipamento"],
        serie=serie,
    )
    db_session.add(ec); db_session.commit(); db_session.refresh(ec)
    return ec


def _equipamento_modulo(db_session):
    """Cria um Equipamento (catalogo) e aponta EQUIPAMENTO_MODULO_ID pra ele, restaurando depois."""
    from app.models import Equipamento
    from app.core.config import settings
    eq = Equipamento(descricao="Modulo de Calibracao PHOEBUS")
    db_session.add(eq); db_session.commit(); db_session.refresh(eq)
    anterior = settings.EQUIPAMENTO_MODULO_ID
    settings.EQUIPAMENTO_MODULO_ID = eq.id
    return eq, anterior


def _instalar(db_session, modulo_id, phoebus_id, saiu_em=None):
    from app.models import InstalacaoModulo
    i = InstalacaoModulo(modulo=modulo_id, phoebus=phoebus_id, entrou_em=date(2026, 7, 18),
                         saiu_em=saiu_em, origem="teste")
    db_session.add(i); db_session.commit()
    return i


def test_phoebus_mostra_modulo_instalado(client, usuario_comum, os_base, db_session):
    pho = _equip(db_session, os_base, "WATFR01-00257")
    mod = _equip(db_session, os_base, "F004230")
    _instalar(db_session, mod.id, pho.id)
    h = _headers(client, "comum@hs.com", "senha123")
    body = client.get(f"/equipamentos-cliente/{pho.id}", headers=h).json()
    assert body["modulo_instalado"]["id"] == mod.id
    assert body["modulo_instalado"]["serie"] == "F004230"
    assert body["instalado_em"] is None


def test_modulo_mostra_onde_esta_instalado(client, usuario_comum, os_base, db_session):
    pho = _equip(db_session, os_base, "WATFR01-00257")
    mod = _equip(db_session, os_base, "F004230")
    _instalar(db_session, mod.id, pho.id)
    h = _headers(client, "comum@hs.com", "senha123")
    body = client.get(f"/equipamentos-cliente/{mod.id}", headers=h).json()
    assert body["instalado_em"]["id"] == pho.id
    assert body["instalado_em"]["serie"] == "WATFR01-00257"
    assert body["instalado_em"]["cliente_nome"] == "Cliente OS"
    assert body["modulo_instalado"] is None


def test_instalacao_fechada_nao_aparece(client, usuario_comum, os_base, db_session):
    """Historico nao vaza como elo atual."""
    pho = _equip(db_session, os_base, "AP-1")
    mod = _equip(db_session, os_base, "MOD-1")
    _instalar(db_session, mod.id, pho.id, saiu_em=date(2026, 7, 18))
    h = _headers(client, "comum@hs.com", "senha123")
    assert client.get(f"/equipamentos-cliente/{pho.id}", headers=h).json()["modulo_instalado"] is None
    assert client.get(f"/equipamentos-cliente/{mod.id}", headers=h).json()["instalado_em"] is None


def test_nao_permite_duas_instalacoes_abertas_do_mesmo_modulo(db_session, os_base):
    from sqlalchemy.exc import IntegrityError
    pho1 = _equip(db_session, os_base, "AP-1"); pho2 = _equip(db_session, os_base, "AP-2")
    mod = _equip(db_session, os_base, "MOD-1")
    _instalar(db_session, mod.id, pho1.id)
    with pytest.raises(IntegrityError):
        _instalar(db_session, mod.id, pho2.id)
    db_session.rollback()


def test_nao_permite_dois_modulos_abertos_no_mesmo_phoebus(db_session, os_base):
    from sqlalchemy.exc import IntegrityError
    pho = _equip(db_session, os_base, "AP-1")
    m1 = _equip(db_session, os_base, "MOD-1"); m2 = _equip(db_session, os_base, "MOD-2")
    _instalar(db_session, m1.id, pho.id)
    with pytest.raises(IntegrityError):
        _instalar(db_session, m2.id, pho.id)
    db_session.rollback()


def test_modulo_sem_instalacao_aberta_esta_em_estoque(client, usuario_comum, os_base, db_session):
    from app.core.config import settings
    eq_mod, anterior = _equipamento_modulo(db_session)
    try:
        mod = _equip(db_session, os_base, "MOD-ESTOQUE", equipamento=eq_mod.id)
        h = _headers(client, "comum@hs.com", "senha123")
        body = client.get(f"/equipamentos-cliente/{mod.id}", headers=h).json()
        assert body["em_estoque"] is True
    finally:
        settings.EQUIPAMENTO_MODULO_ID = anterior


def test_modulo_instalado_nao_esta_em_estoque(client, usuario_comum, os_base, db_session):
    from app.core.config import settings
    eq_mod, anterior = _equipamento_modulo(db_session)
    try:
        pho = _equip(db_session, os_base, "AP-ESTOQUE")
        mod = _equip(db_session, os_base, "MOD-INSTALADO", equipamento=eq_mod.id)
        _instalar(db_session, mod.id, pho.id)
        h = _headers(client, "comum@hs.com", "senha123")
        body = client.get(f"/equipamentos-cliente/{mod.id}", headers=h).json()
        assert body["em_estoque"] is False
    finally:
        settings.EQUIPAMENTO_MODULO_ID = anterior


def test_phoebus_nunca_esta_em_estoque(client, usuario_comum, os_base, db_session):
    pho = _equip(db_session, os_base, "AP-NAO-ESTOQUE")
    h = _headers(client, "comum@hs.com", "senha123")
    body = client.get(f"/equipamentos-cliente/{pho.id}", headers=h).json()
    assert body["em_estoque"] is False


def test_patch_mantem_elo_sem_get_previo(client, usuario_admin, os_base, db_session):
    """Regressao: o PATCH tem que anotar o elo na propria resposta, sem depender
    de um GET anterior ter deixado o atributo carimbado na instancia da sessao."""
    pho = _equip(db_session, os_base, "WATFR01-00257")
    mod = _equip(db_session, os_base, "F004230")
    _instalar(db_session, mod.id, pho.id)
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.patch(f"/equipamentos-cliente/{pho.id}", json={"patrimonio": "PAT-NOVO"}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["patrimonio"] == "PAT-NOVO"
    assert body["modulo_instalado"]["id"] == mod.id


def test_transferir_mantem_elo_sem_get_previo(client, usuario_admin, os_base, db_session):
    from app.models import Cliente
    pho = _equip(db_session, os_base, "WATFR01-00257")
    mod = _equip(db_session, os_base, "F004230")
    _instalar(db_session, mod.id, pho.id)
    destino = Cliente(nome="Empresa Nova")
    db_session.add(destino); db_session.commit(); db_session.refresh(destino)
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.post(f"/equipamentos-cliente/{pho.id}/transferir",
                    json={"cliente": destino.id}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["cliente"] == destino.id
    assert body["modulo_instalado"]["id"] == mod.id


def test_criar_nao_tem_elo(client, usuario_admin, os_base):
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.post("/equipamentos-cliente", json={
        "cliente": os_base["cliente"], "equipamento": os_base["equipamento"], "serie": "NOVO-SEM-ELO",
    }, headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["modulo_instalado"] is None
    assert body["instalado_em"] is None
    assert body["em_estoque"] is False
