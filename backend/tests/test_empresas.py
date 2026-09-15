import pytest

from app.core import empresa_servico as es
from app.core.empresa import DocumentoInvalido
from app.models import Cliente, Empresa
from app.schemas.empresa import EmpresaIn

CNPJ_A = "08857492000148"
CNPJ_B = "36312056000552"
CNPJ_C = "11222333000181"


def _in(**kw):
    base = dict(documento=CNPJ_B, nome="Filial", cliente=None)
    base.update(kw)
    return EmpresaIn(**base)


# --- servico ----------------------------------------------------------------

def test_criar_empresa_normaliza_documento_e_liga_matriz(db_session):
    cli = Cliente(nome="ACME", cgc=CNPJ_A); db_session.add(cli); db_session.flush()
    e = es.criar_empresa(db_session, _in(documento="36.312.056/0005-52", cliente=cli.id, estado="pe", cep="29680-000"))
    assert e.id is not None
    assert (e.cgc, e.cpf) == (CNPJ_B, None)
    assert e.estado == "PE" and e.cep == "29680000"
    assert e.cliente == cli.id


def test_criar_empresa_com_cpf(db_session):
    e = es.criar_empresa(db_session, _in(documento="123.456.789-09"))
    assert (e.cgc, e.cpf) == (None, "12345678909")


def test_criar_empresa_documento_invalido(db_session):
    with pytest.raises(DocumentoInvalido):
        es.criar_empresa(db_session, _in(documento="08857492000149"))


def test_criar_empresa_documento_de_cliente_e_duplicado(db_session):
    cli = Cliente(nome="ACME", cgc=CNPJ_B); db_session.add(cli); db_session.flush()
    with pytest.raises(es.DocumentoDuplicado) as exc:
        es.criar_empresa(db_session, _in())
    assert exc.value.tipo == "cliente" and exc.value.id == cli.id
    assert str(exc.value) == "Documento já cadastrado como Cliente: ACME"


def test_criar_empresa_documento_de_outra_empresa_e_duplicado(db_session):
    es.criar_empresa(db_session, _in(nome="Primeira"))
    with pytest.raises(es.DocumentoDuplicado) as exc:
        es.criar_empresa(db_session, _in(nome="Segunda"))
    assert exc.value.tipo == "empresa"


def test_criar_empresa_matriz_inexistente(db_session):
    with pytest.raises(es.MatrizInexistente):
        es.criar_empresa(db_session, _in(cliente=999))


def test_atualizar_empresa_mantendo_o_proprio_documento(db_session):
    e = es.criar_empresa(db_session, _in())
    es.atualizar_empresa(db_session, e, _in(nome="Renomeada", bairro="Centro"))
    assert e.nome == "Renomeada" and e.bairro == "Centro"


def test_atualizar_empresa_para_documento_ocupado(db_session):
    es.criar_empresa(db_session, _in(documento=CNPJ_C, nome="Outra"))
    e = es.criar_empresa(db_session, _in())
    with pytest.raises(es.DocumentoDuplicado):
        es.atualizar_empresa(db_session, e, _in(documento=CNPJ_C))


def test_checagem_do_lado_do_cliente_ignora_duplicata_entre_clientes(db_session):
    # Duplicata antiga entre clientes nao pode travar a edicao do cliente.
    db_session.add_all([Cliente(nome="A", cgc=CNPJ_A), Cliente(nome="B", cgc=CNPJ_A)]); db_session.flush()
    es.checar_documento_livre(db_session, CNPJ_A, None, incluir_clientes=False)


def test_schema_campos_vazios_viram_none():
    d = _in(email="  ", bairro="")
    assert d.email is None and d.bairro is None


# --- rotas ------------------------------------------------------------------

def _payload(**kw):
    base = {"documento": CNPJ_B, "nome": "Filial Norte", "cliente": None,
            "municipio": "Recife", "estado": "PE"}
    base.update(kw)
    return base


def test_comercial_cria_e_le_empresa(client_comercial, db_session):
    cli = Cliente(nome="ACME", cgc=CNPJ_A); db_session.add(cli); db_session.commit()
    r = client_comercial.post("/empresas", json=_payload(cliente=cli.id))
    assert r.status_code == 201, r.text
    corpo = r.json()
    assert corpo["cgc"] == CNPJ_B and corpo["matriz_nome"] == "ACME" and corpo["ativo"] is True
    r = client_comercial.get(f"/empresas/{corpo['id']}")
    assert r.status_code == 200 and r.json()["nome"] == "Filial Norte"


def test_financeiro_cria_empresa(client_fin):
    assert client_fin.post("/empresas", json=_payload()).status_code == 201


def test_laboratorio_le_mas_nao_escreve(client_lab, db_session):
    db_session.add(Empresa(nome="Existente", cgc=CNPJ_C)); db_session.commit()
    assert client_lab.get("/empresas").status_code == 200
    assert client_lab.post("/empresas", json=_payload()).status_code == 403


def test_documento_invalido_422(client_comercial):
    r = client_comercial.post("/empresas", json=_payload(documento="08857492000149"))
    assert r.status_code == 422
    assert r.json()["detail"] == "CNPJ invalido"


def test_documento_de_cliente_409(client_comercial, db_session):
    db_session.add(Cliente(nome="ACME", cgc=CNPJ_B)); db_session.commit()
    r = client_comercial.post("/empresas", json=_payload())
    assert r.status_code == 409
    assert r.json()["detail"] == "Documento já cadastrado como Cliente: ACME"


def test_matriz_inexistente_422(client_comercial):
    assert client_comercial.post("/empresas", json=_payload(cliente=999)).status_code == 422


def test_listar_filtra_por_busca_matriz_e_ativo(client_comercial, db_session):
    cli = Cliente(nome="ACME", cgc=CNPJ_A); db_session.add(cli); db_session.flush()
    db_session.add_all([
        Empresa(nome="Filial Norte", cgc=CNPJ_B, cliente=cli.id),
        Empresa(nome="Outra Coisa", cgc=CNPJ_C, ativo=False),
    ]); db_session.commit()
    assert client_comercial.get("/empresas?q=norte").json()["total"] == 1
    assert client_comercial.get("/empresas?q=36.312.056").json()["total"] == 1
    assert client_comercial.get(f"/empresas?cliente={cli.id}").json()["total"] == 1
    assert client_comercial.get("/empresas?ativo=false").json()["items"][0]["nome"] == "Outra Coisa"
    assert client_comercial.get("/empresas").json()["total"] == 2


def test_put_atualiza_e_desativar_reativar(client_comercial):
    eid = client_comercial.post("/empresas", json=_payload()).json()["id"]
    r = client_comercial.put(f"/empresas/{eid}", json=_payload(nome="Filial Sul", bairro="Centro"))
    assert r.status_code == 200 and r.json()["nome"] == "Filial Sul"
    assert client_comercial.post(f"/empresas/{eid}/desativar").json()["ativo"] is False
    assert client_comercial.post(f"/empresas/{eid}/reativar").json()["ativo"] is True


def test_put_inexistente_404(client_comercial):
    assert client_comercial.put("/empresas/999", json=_payload()).status_code == 404
