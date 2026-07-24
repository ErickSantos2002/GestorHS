def test_models_proposta_basico(db_session):
    from app.models import Cliente, Proposta, PropostaItem
    cli = Cliente(nome="ACME"); db_session.add(cli); db_session.flush()
    p = Proposta(numero=1, cliente=cli.id, vendedor="Fulano")
    p.itens.append(PropostaItem(descricao="Calibracao", quantidade=2, preco_un=395, total=790))
    db_session.add(p); db_session.flush()
    assert p.numero == 1
    assert p.itens[0].total == 790
    assert p.is_deleted is False


def test_schema_proposta_create_valida():
    from app.schemas.proposta import PropostaCreate, PropostaItemCreate, PropostaAparelhoCreate

    payload = PropostaCreate(
        cliente=1,
        itens=[PropostaItemCreate(descricao="Calibracao de bafometro", quantidade=2, preco_un=395)],
        aparelhos=[PropostaAparelhoCreate(equipamento_cliente=10)],
    )
    assert payload.cliente == 1
    assert payload.itens[0].descricao == "Calibracao de bafometro"
    assert payload.aparelhos[0].equipamento_cliente == 10
    # itens/aparelhos tem default_factory=list quando omitidos
    assert PropostaCreate(cliente=1).itens == []
    assert PropostaCreate(cliente=1).aparelhos == []


def test_schema_proposta_update_todos_campos_opcionais():
    from app.schemas.proposta import PropostaUpdate

    # nenhum campo obrigatorio: instanciar vazio nao deve levantar
    vazio = PropostaUpdate()
    assert vazio.cliente is None
    assert vazio.itens is None
    assert vazio.aparelhos is None

    parcial = PropostaUpdate(desconto=10, observacoes="ajustado")
    assert parcial.desconto == 10
    assert parcial.observacoes == "ajustado"
    assert parcial.vendedor is None


def test_schema_proposta_out_from_attributes(db_session):
    from app.models import Cliente, Proposta, PropostaItem, PropostaAparelho
    from app.schemas.proposta import PropostaOut

    cli = Cliente(nome="ACME", cgc="12345678000199")
    db_session.add(cli); db_session.flush()

    p = Proposta(numero=42, cliente=cli.id, vendedor="Fulano")
    p.itens.append(PropostaItem(descricao="Calibracao", quantidade=1, preco_un=100, total=100))
    p.aparelhos.append(PropostaAparelho(equipamento_cliente=None, serie="ABC123", modelo="X1"))
    db_session.add(p); db_session.flush()

    out = PropostaOut.model_validate(p)
    assert out.id == p.id
    assert out.numero == 42
    assert out.itens[0].descricao == "Calibracao"
    assert out.aparelhos[0].serie == "ABC123"


def test_schema_proposta_versao_out_from_attributes(db_session):
    from app.models import Proposta, PropostaVersao
    from app.schemas.proposta import PropostaVersaoOut

    p = Proposta(numero=99, vendedor="Fulano")
    db_session.add(p); db_session.flush()

    v = PropostaVersao(proposta=p.id, numero_versao=1, alterado_por="Fulano", snapshot={"a": 1})
    db_session.add(v); db_session.flush()

    # has_pdf nao existe na model (so pdf_path); o campo derivado cai no default
    # (False) quando validado direto do objeto do model — quem monta o card real
    # (router, fora do escopo desta task) passa has_pdf explicito via dict/dump.
    out = PropostaVersaoOut.model_validate(v)
    assert out.numero_versao == 1
    assert out.alterado_por == "Fulano"
    assert out.has_pdf is False
    assert out.snapshot == {"a": 1}


def test_proximo_numero_incrementa(db_session):
    from app.core import proposta_servico as ps
    from app.models import Proposta

    assert ps.proximo_numero(db_session) == 1
    db_session.add(Proposta(numero=5, vendedor="Fulano"))
    db_session.flush()
    assert ps.proximo_numero(db_session) == 6


def test_criar_proposta_calcula_total_e_numero(db_session):
    from app.core import proposta_servico as ps
    from app.schemas.proposta import PropostaCreate, PropostaItemCreate
    from app.models import Cliente

    cli = Cliente(nome="ACME"); db_session.add(cli); db_session.flush()
    dados = PropostaCreate(
        cliente=cli.id,
        itens=[PropostaItemCreate(descricao="Calib", quantidade=2, preco_un=395)],
    )
    p = ps.criar_proposta(db_session, dados, vendedor="Fulano")
    assert p.numero == 1
    assert p.vendedor == "Fulano"
    assert float(p.itens[0].total) == 790.0

    out = ps.montar_saida(db_session, p)
    assert out.total == 790.0
    assert out.total_itens == 790.0
    assert out.cliente_nome == "ACME"


def test_criar_proposta_com_aparelho_puxa_snapshot_da_frota(db_session):
    from datetime import date
    from app.core import proposta_servico as ps
    from app.schemas.proposta import PropostaCreate, PropostaAparelhoCreate
    from app.models import Cliente, Equipamento, EquipamentoCliente

    cli = Cliente(nome="ACME"); db_session.add(cli); db_session.flush()
    equip = Equipamento(descricao="Bafometro X1"); db_session.add(equip); db_session.flush()
    ec = EquipamentoCliente(
        cliente=cli.id, equipamento=equip.id, serie="ABC123", patrimonio="PAT-1",
        prox_calibragem=date(2026, 12, 1),
    )
    db_session.add(ec); db_session.flush()

    dados = PropostaCreate(cliente=cli.id, aparelhos=[PropostaAparelhoCreate(equipamento_cliente=ec.id)])
    p = ps.criar_proposta(db_session, dados, vendedor="Fulano")

    assert p.aparelhos[0].serie == "ABC123"
    assert p.aparelhos[0].modelo == "Bafometro X1"
    assert p.aparelhos[0].patrimonio == "PAT-1"
    assert p.aparelhos[0].prox_calibragem == date(2026, 12, 1)


def test_montar_saida_respeita_cliente_override(db_session):
    from app.core import proposta_servico as ps
    from app.models import Cliente, Proposta

    cli = Cliente(nome="ACME", cgc="12345678000199"); db_session.add(cli); db_session.flush()
    p = Proposta(numero=1, cliente=cli.id, vendedor="Fulano",
                 cliente_override={"nome": "ACME Filial", "documento": "99988877000166"})
    db_session.add(p); db_session.flush()

    out = ps.montar_saida(db_session, p)
    assert out.cliente_nome == "ACME Filial"
    assert out.cliente_documento == "99988877000166"


def test_atualizar_proposta_cria_versao_sem_sobrescrever_vendedor(db_session, monkeypatch):
    from app.core import proposta_servico as ps
    from app.core import proposta_pdf
    from app.schemas.proposta import PropostaCreate, PropostaUpdate

    # Nao chama Playwright no teste: arquivar_pdf_versao vira no-op.
    monkeypatch.setattr(proposta_pdf, "arquivar_pdf_versao", lambda *a, **k: None)

    p = ps.criar_proposta(db_session, PropostaCreate(cliente=None), vendedor="Fulano")
    assert len(p.versoes) == 0

    atualizado = ps.atualizar_proposta(
        db_session, p, PropostaUpdate(desconto=10, vendedor="Outro Nome"), alterado_por="Ciclano",
    )

    assert len(atualizado.versoes) == 1
    assert atualizado.versoes[0].numero_versao == 1
    assert atualizado.versoes[0].alterado_por == "Ciclano"
    assert atualizado.versoes[0].pdf_path is None
    assert float(atualizado.desconto) == 10
    # vendedor e imutavel: update nao sobrescreve.
    assert atualizado.vendedor == "Fulano"


def test_atualizar_proposta_substitui_itens_quando_informado(db_session, monkeypatch):
    from app.core import proposta_servico as ps
    from app.core import proposta_pdf
    from app.schemas.proposta import PropostaCreate, PropostaItemCreate, PropostaUpdate

    monkeypatch.setattr(proposta_pdf, "arquivar_pdf_versao", lambda *a, **k: None)

    dados = PropostaCreate(itens=[PropostaItemCreate(descricao="Item A", quantidade=1, preco_un=100)])
    p = ps.criar_proposta(db_session, dados, vendedor="Fulano")
    assert len(p.itens) == 1

    atualizado = ps.atualizar_proposta(
        db_session, p,
        PropostaUpdate(itens=[PropostaItemCreate(descricao="Item B", quantidade=3, preco_un=50)]),
        alterado_por="Ciclano",
    )
    assert len(atualizado.itens) == 1
    assert atualizado.itens[0].descricao == "Item B"
    assert float(atualizado.itens[0].total) == 150.0


def test_atualizar_proposta_nao_zera_desconto_com_none(db_session, monkeypatch):
    from app.core import proposta_servico as ps
    from app.core import proposta_pdf
    from app.schemas.proposta import PropostaCreate, PropostaUpdate

    monkeypatch.setattr(proposta_pdf, "arquivar_pdf_versao", lambda *a, **k: None)

    dados = PropostaCreate(desconto=25)
    p = ps.criar_proposta(db_session, dados, vendedor="Fulano")
    assert float(p.desconto) == 25

    # PropostaUpdate() com tudo None + exclude_unset: nao toca no desconto.
    atualizado = ps.atualizar_proposta(db_session, p, PropostaUpdate(), alterado_por="Ciclano")
    assert float(atualizado.desconto) == 25


def test_snapshot_proposta_traz_itens_e_totais(db_session):
    from app.core import proposta_servico as ps
    from app.models import Cliente, Proposta, PropostaItem

    cli = Cliente(nome="ACME"); db_session.add(cli); db_session.flush()
    p = Proposta(numero=7, cliente=cli.id, vendedor="Fulano", frete=10, desconto=5)
    p.itens.append(PropostaItem(descricao="Calib", quantidade=1, preco_un=100, total=100))
    db_session.add(p); db_session.flush()

    snap = ps.snapshot_proposta(p)
    assert snap["numero"] == 7
    assert snap["cliente_nome"] == "ACME"
    assert snap["total_itens"] == 100.0
    assert snap["total"] == 105.0
    assert snap["itens"][0]["descricao"] == "Calib"


# ---------------------------------------------------------------------------
# API (router) — Task 8
# ---------------------------------------------------------------------------

def test_api_criar_proposta_sem_auth_e_negado(client):
    # client_comercial mutaria os headers do mesmo TestClient (mesmo padrao de
    # client_lab/client_fin/client_exp): combinar as duas fixtures faria o setup
    # do client_comercial rodar antes do corpo do teste e a chamada "sem auth"
    # ja sairia com o token — por isso o caso sem auth vira teste proprio.
    r = client.post("/propostas", json={"itens": []})
    assert r.status_code in (401, 403)


def test_api_criar_proposta_funcao_errada_e_negado(client_exp):
    r = client_exp.post("/propostas", json={"itens": []})
    assert r.status_code == 403


def test_api_criar_e_listar_proposta(client_comercial, db_session):
    from app.models import Cliente
    cli = Cliente(nome="ACME")
    db_session.add(cli); db_session.commit(); db_session.refresh(cli)

    r = client_comercial.post("/propostas", json={
        "cliente": cli.id,
        "itens": [{"descricao": "Calibracao", "quantidade": 2, "preco_un": 395}],
    })
    assert r.status_code == 201
    criada = r.json()
    assert criada["numero"] == 1
    assert criada["vendedor"] == "Comercial"
    assert criada["total"] == 790.0
    assert criada["cliente_nome"] == "ACME"

    r = client_comercial.get("/propostas")
    assert r.status_code == 200
    pagina = r.json()
    assert pagina["total"] == 1
    assert pagina["total_pages"] == 1
    assert pagina["items"][0]["id"] == criada["id"]

    # filtro q por nome do cliente
    assert client_comercial.get("/propostas", params={"q": "ACME"}).json()["total"] == 1
    assert client_comercial.get("/propostas", params={"q": "Nao Existe"}).json()["total"] == 0
    # filtro q pelo numero
    assert client_comercial.get("/propostas", params={"q": "1"}).json()["total"] == 1


def test_api_obter_proposta_inexistente_e_404(client_comercial):
    r = client_comercial.get("/propostas/9999")
    assert r.status_code == 404


def test_api_atualizar_proposta_versiona_e_lista_versoes(client_comercial, monkeypatch):
    from app.core import proposta_pdf
    monkeypatch.setattr(proposta_pdf, "arquivar_pdf_versao", lambda *a, **k: None)

    r = client_comercial.post("/propostas", json={"itens": []})
    pid = r.json()["id"]

    r = client_comercial.put(f"/propostas/{pid}", json={"desconto": 15})
    assert r.status_code == 200
    assert r.json()["desconto"] == 15
    # vendedor e imutavel: update nao aceita sobrescrever
    assert r.json()["vendedor"] == "Comercial"

    r = client_comercial.get(f"/propostas/{pid}/versoes")
    assert r.status_code == 200
    versoes = r.json()
    assert len(versoes) == 1
    assert versoes[0]["numero_versao"] == 1
    assert versoes[0]["has_pdf"] is False


def test_api_duplicar_proposta_gera_numero_novo_e_copia_itens(client_comercial, db_session):
    from app.models import Cliente
    cli = Cliente(nome="ACME")
    db_session.add(cli); db_session.commit(); db_session.refresh(cli)

    r = client_comercial.post("/propostas", json={
        "cliente": cli.id,
        "itens": [{"descricao": "Calibracao", "quantidade": 2, "preco_un": 395}],
    })
    original = r.json()

    r = client_comercial.post(f"/propostas/{original['id']}/duplicar")
    assert r.status_code == 201
    nova = r.json()
    assert nova["id"] != original["id"]
    assert nova["numero"] != original["numero"]
    assert nova["vendedor"] == "Comercial"
    assert len(nova["itens"]) == 1
    assert nova["itens"][0]["descricao"] == "Calibracao"

    r = client_comercial.get(f"/propostas/{nova['id']}/versoes")
    assert r.status_code == 200
    assert r.json() == []


def test_api_delete_soft_delete_some_da_lista(client_comercial):
    r = client_comercial.post("/propostas", json={"itens": []})
    pid = r.json()["id"]

    r = client_comercial.delete(f"/propostas/{pid}")
    assert r.status_code == 204

    r = client_comercial.get("/propostas")
    ids = [p["id"] for p in r.json()["items"]]
    assert pid not in ids

    assert client_comercial.get(f"/propostas/{pid}").status_code == 404
    assert client_comercial.delete(f"/propostas/{pid}").status_code == 404


def test_api_pdf_endpoint_inline_e_attachment(client_comercial, monkeypatch):
    from app.core import proposta_pdf
    monkeypatch.setattr(proposta_pdf, "gerar_pdf", lambda *a, **k: b"%PDF-1.4 fake")

    r = client_comercial.post("/propostas", json={"itens": []})
    pid = r.json()["id"]

    r = client_comercial.get(f"/propostas/{pid}/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "inline" in r.headers["content-disposition"]

    r = client_comercial.get(f"/propostas/{pid}/pdf", params={"download": 1})
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]


def test_api_pdf_endpoint_proposta_inexistente_e_404(client_comercial):
    assert client_comercial.get("/propostas/9999/pdf").status_code == 404


def test_api_versao_pdf_endpoint(client_comercial, monkeypatch):
    from app.core import proposta_pdf
    monkeypatch.setattr(proposta_pdf, "arquivar_pdf_versao",
                         lambda db, proposta, numero_versao: f"propostas/{proposta.id}/v{numero_versao}.pdf")
    monkeypatch.setattr(proposta_pdf, "ler_pdf_versao", lambda pdf_path: b"%PDF-1.4 fake-versao")

    r = client_comercial.post("/propostas", json={"itens": []})
    pid = r.json()["id"]
    client_comercial.put(f"/propostas/{pid}", json={"desconto": 20})

    versao_id = client_comercial.get(f"/propostas/{pid}/versoes").json()[0]["id"]

    r = client_comercial.get(f"/propostas/{pid}/versoes/{versao_id}/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"

    assert client_comercial.get(f"/propostas/{pid}/versoes/9999/pdf").status_code == 404
