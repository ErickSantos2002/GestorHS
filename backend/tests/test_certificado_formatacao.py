"""CNPJ/CPF mascarados e CEP no endereco — nos tres caminhos de certificado
(OS, venda e avulso), que compartilham o mesmo `_montar_contexto`."""
from datetime import date


def _cliente(db_session, **kw):
    from app.models import Cliente
    base = dict(nome="ACME Ltda", cgc="11222333000144", endereco="Rua X",
                numero=10, bairro="Centro", municipio="Recife", estado="PE",
                cep="50000123")
    base.update(kw)
    cli = Cliente(**base)
    db_session.add(cli); db_session.commit(); db_session.refresh(cli)
    return cli


# --- helpers puros -----------------------------------------------------------

def test_fmt_doc_mascara_cnpj_e_cpf():
    from app.core.certificado_gerar import _fmt_doc
    assert _fmt_doc("11222333000144") == "11.222.333/0001-44"
    assert _fmt_doc("12345678901") == "123.456.789-01"


def test_fmt_doc_aceita_valor_ja_mascarado():
    from app.core.certificado_gerar import _fmt_doc
    assert _fmt_doc("11.222.333/0001-44") == "11.222.333/0001-44"


def test_fmt_doc_deixa_passar_o_que_nao_e_documento():
    """Cadastro sujo nao pode virar mascara errada — sai como veio."""
    from app.core.certificado_gerar import _fmt_doc
    assert _fmt_doc("999") == "999"
    assert _fmt_doc("") == ""
    assert _fmt_doc(None) == ""


def test_fmt_cep_mascara_e_tolera_lixo():
    from app.core.certificado_gerar import _fmt_cep
    assert _fmt_cep("50000123") == "50000-123"
    assert _fmt_cep("50000-123") == "50000-123"
    assert _fmt_cep("123") == "123"
    assert _fmt_cep(None) == ""


# --- endereco ----------------------------------------------------------------

def test_endereco_termina_com_o_cep(db_session):
    from app.core.certificado_gerar import _endereco
    assert _endereco(_cliente(db_session)) == \
        "Rua X, 10, Centro, Recife - PE, CEP 50000-123"


def test_endereco_sem_cep_nao_deixa_sobra(db_session):
    from app.core.certificado_gerar import _endereco
    assert _endereco(_cliente(db_session, cep=None)) == "Rua X, 10, Centro, Recife - PE"


# --- os tres caminhos --------------------------------------------------------

def test_contexto_os(db_session):
    from app.models import Ordem
    from app.core.certificado_gerar import montar_contexto
    cli = _cliente(db_session)
    o = Ordem(cliente=cli.id, situacao="E")
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    ctx = montar_contexto(db_session, o)
    assert ctx["cnpj"] == "11.222.333/0001-44"
    assert ctx["endcli"].endswith("CEP 50000-123")


def test_contexto_os_mascara_override_digitado(db_session):
    """O override vem do modal, cru — mascarar depois de aplica-lo."""
    from app.models import Ordem
    from app.core.certificado_gerar import montar_contexto
    cli = _cliente(db_session)
    o = Ordem(cliente=cli.id, situacao="E", cert_overrides={"cnpj": "99888777000166"})
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    assert montar_contexto(db_session, o)["cnpj"] == "99.888.777/0001-66"


def test_contexto_venda(db_session):
    from app.models import Equipamento, EquipamentoCliente, Marca
    from app.core.certificado_gerar import montar_contexto_venda
    cli = _cliente(db_session)
    m = Marca(descricao="Alcoscan"); db_session.add(m); db_session.flush()
    eq = Equipamento(descricao="Mark X", marca=m.id)
    db_session.add(eq); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="S1",
                            datacompra=date(2026, 1, 5))
    db_session.add(ec); db_session.commit(); db_session.refresh(ec)
    ctx = montar_contexto_venda(db_session, ec, {})
    assert ctx["cnpj"] == "11.222.333/0001-44"
    assert ctx["endcli"].endswith("CEP 50000-123")


def test_contexto_avulso_mascara_o_que_foi_digitado(db_session):
    from app.core.certificado_gerar import montar_contexto_avulso
    ctx = montar_contexto_avulso(db_session, {"cnpj": "11222333000144"})
    assert ctx["cnpj"] == "11.222.333/0001-44"
