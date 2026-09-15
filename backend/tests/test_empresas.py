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
