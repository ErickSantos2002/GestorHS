def _headers(client, email, senha):
    tok = client.post("/auth/login", json={"email": email, "senha": senha}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def test_abrir_os_sucesso(client, usuario_comum, fases_seed, os_base, caixa_base, db_session):
    # usuario_comum = Expedição
    h = _headers(client, "comum@hs.com", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
        "caixa": caixa_base,
        "condicao_chegada": "Com avarias",
    }, headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["fase"] == 4
    assert body["cliente"] == os_base["cliente"]      # derivado do equipamento
    assert body["recebido"] is True
    assert body["data_chegada"] is not None
    # os_atual atualizado no equipamento
    from app.models import EquipamentoCliente
    ec = db_session.get(EquipamentoCliente, os_base["equipamento_cliente"])
    db_session.refresh(ec)
    assert ec.os_atual == body["id"]
    # log de abertura
    logs = client.get(f"/ordens/{body['id']}/logs", headers=h).json()
    assert len(logs) == 1


def test_abrir_os_admin_tambem_pode(client, usuario_admin, fases_seed, os_base, caixa_base):
    h = _headers(client, "admin@hs.com", "senha123")
    r = client.post("/ordens", json={"equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "M", "caixa": caixa_base}, headers=h)
    assert r.status_code == 201


def test_abrir_os_equipamento_inexistente_404(client, usuario_comum, fases_seed):
    h = _headers(client, "comum@hs.com", "senha123")
    assert client.post("/ordens", json={"equipamento_cliente": 9999, "tipo_servico": "C"}, headers=h).status_code == 404


def test_abrir_os_duplicada_409(client, usuario_comum, fases_seed, os_base, caixa_base):
    h = _headers(client, "comum@hs.com", "senha123")
    p = {"equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C", "caixa": caixa_base}
    assert client.post("/ordens", json=p, headers=h).status_code == 201
    assert client.post("/ordens", json=p, headers=h).status_code == 409  # já tem OS ativa


def test_abrir_os_exige_expedicao_ou_admin(client, usuario_admin, usuario_lab, fases_seed, os_base):
    h = _headers(client, "lab@hs.com", "senha123")
    assert client.post("/ordens", json={"equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C"}, headers=h).status_code == 403


def test_abrir_os_com_caixa(client, usuario_comum, fases_seed, os_base):
    h = _headers(client, "comum@hs.com", "senha123")
    cid = client.post("/caixas", json={"obs": "lote"}, headers=h).json()["id"]
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"],
        "tipo_servico": "C", "caixa": cid,
    }, headers=h)
    assert r.status_code == 201
    assert r.json()["caixa"] == cid
    det = client.get(f"/caixas/{cid}", headers=h).json()
    assert det["total_os"] == 1


def test_abrir_os_caixa_inexistente_404(client, usuario_comum, fases_seed, os_base):
    h = _headers(client, "comum@hs.com", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"],
        "tipo_servico": "C", "caixa": 9999,
    }, headers=h)
    assert r.status_code == 404


def test_abrir_grava_recebimento(client, usuario_comum, fases_seed, os_base, caixa_base, db_session):
    h = _headers(client, "comum@hs.com", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"],
        "tipo_servico": "C",
        "caixa": caixa_base,
        "data_chegada": "2026-06-08",
        "condicao_chegada": "Bom estado",
        "checklist": [3, 1],
        "pilhas": 4,
        "bocais": 2,
        "observacoes": "veio sem maleta",
    }, headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["condicao_chegada"] == "Bom estado"
    assert body["checklist_ids"] == [1, 3]
    assert body["acessorios_presentes"] == ["Bobinas", "Cabos USB"]
    assert body["pilhas"] == 4
    assert body["bocais"] == 2
    assert body["obs"] == "veio sem maleta"
    assert body["data_chegada"].startswith("2026-06-08")


def test_abrir_data_chegada_default_hoje(client, usuario_comum, fases_seed, os_base, caixa_base):
    h = _headers(client, "comum@hs.com", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "M",
        "caixa": caixa_base,
    }, headers=h)
    assert r.status_code == 201
    assert r.json()["data_chegada"] is not None


def test_abrir_condicao_invalida_400(client, usuario_comum, fases_seed, os_base, caixa_base):
    h = _headers(client, "comum@hs.com", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
        "caixa": caixa_base,
        "condicao_chegada": "INEXISTENTE",
    }, headers=h)
    assert r.status_code == 400


def test_abrir_checklist_id_invalido_400(client, usuario_comum, fases_seed, os_base, caixa_base):
    h = _headers(client, "comum@hs.com", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
        "caixa": caixa_base,
        "checklist": [1, 99],
    }, headers=h)
    assert r.status_code == 400


def test_abrir_os_sem_caixa_cria_a_caixa(client, usuario_comum, fases_seed, os_base):
    """Antes isto era 400. A caixa passou a nascer junto com a OS — ver os testes
    no fim do arquivo, que cobrem o numero e a atomicidade."""
    h = _headers(client, "comum@hs.com", "senha123")
    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
    }, headers=h)
    assert r.status_code == 201
    assert r.json()["caixa"] is not None


# ── Caixa criada junto com a OS ──────────────────────────────────────────────
# Sem caixa informada, a caixa nasce COM a OS dentro. Antes era erro 400: a
# pessoa tinha que criar a caixa antes, por outra tela, sem saber qual seria o
# proximo numero — e se desistisse no meio, a caixa vazia ficava para tras.

def test_abrir_sem_caixa_cria_uma_com_a_os_dentro(client, usuario_comum, fases_seed, os_base, db_session):
    from app.models import Caixa
    h = _headers(client, "comum@hs.com", "senha123")
    antes = db_session.query(Caixa).count()

    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
    }, headers=h)

    assert r.status_code == 201
    corpo = r.json()
    assert corpo["caixa"] is not None, "a OS nunca pode nascer sem caixa"
    db_session.expire_all()
    assert db_session.query(Caixa).count() == antes + 1

    det = client.get(f"/caixas/{corpo['caixa']}", headers=h).json()
    assert det["total_os"] == 1
    assert det["fase"] == 4, "a caixa nasce na mesma fase da OS"


def test_caixa_criada_recebe_o_proximo_numero(client, usuario_comum, fases_seed, os_base, db_session):
    """O numero da caixa E' o id — quem atribui e' o banco, entao nao ha consulta
    de "qual e o proximo" nem corrida entre duas aberturas simultaneas."""
    from app.models import Caixa
    h = _headers(client, "comum@hs.com", "senha123")
    maior = db_session.query(Caixa).order_by(Caixa.id.desc()).first()
    esperado = (maior.id if maior else 0) + 1

    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
    }, headers=h)
    assert r.json()["caixa"] == esperado


def test_caixa_informada_continua_sendo_usada(client, usuario_comum, fases_seed, os_base, db_session):
    from app.models import Caixa
    h = _headers(client, "comum@hs.com", "senha123")
    cid = client.post("/caixas", json={"obs": "lote existente"}, headers=h).json()["id"]
    antes = db_session.query(Caixa).count()

    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C", "caixa": cid,
    }, headers=h)

    assert r.json()["caixa"] == cid
    db_session.expire_all()
    assert db_session.query(Caixa).count() == antes, "nao pode criar caixa quando uma foi informada"


def test_falha_na_abertura_nao_deixa_caixa_vazia(client, usuario_comum, fases_seed, os_base, db_session):
    """A caixa so existe se a OS existir — e o motivo de a criacao ter vindo
    para dentro da abertura, em vez de ser um passo separado."""
    from app.models import Caixa
    h = _headers(client, "comum@hs.com", "senha123")
    # Abre uma vez com sucesso; a segunda falha com 409 (aparelho ja tem OS ativa).
    client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
    }, headers=h)
    db_session.expire_all()
    antes = db_session.query(Caixa).count()

    r = client.post("/ordens", json={
        "equipamento_cliente": os_base["equipamento_cliente"], "tipo_servico": "C",
    }, headers=h)
    assert r.status_code == 409
    db_session.expire_all()
    assert db_session.query(Caixa).count() == antes, "a recusa nao pode deixar caixa orfa"
