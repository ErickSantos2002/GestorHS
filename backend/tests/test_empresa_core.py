from types import SimpleNamespace

import pytest

from app.core import empresa


def test_cnpj_valido():
    assert empresa.cnpj_valido("08857492000148")
    assert empresa.cnpj_valido("36312056000552")
    assert not empresa.cnpj_valido("08857492000149")
    assert not empresa.cnpj_valido("11111111111111")
    assert not empresa.cnpj_valido("0885749200014")


def test_cpf_valido():
    assert empresa.cpf_valido("12345678909")
    assert empresa.cpf_valido("11144477735")
    assert not empresa.cpf_valido("12345678900")
    assert not empresa.cpf_valido("00000000000")


def test_normalizar_documento_cnpj_com_mascara():
    assert empresa.normalizar_documento("08.857.492/0001-48") == ("08857492000148", None)


def test_normalizar_documento_cpf():
    assert empresa.normalizar_documento("123.456.789-09") == (None, "12345678909")


@pytest.mark.parametrize("texto", ["", None, "123", "08857492000149", "12345678900"])
def test_normalizar_documento_invalido(texto):
    with pytest.raises(empresa.DocumentoInvalido):
        empresa.normalizar_documento(texto)


def _cliente(**kw):
    base = dict(id=5, nome="ACME", cgc="08857492000148", cpf=None, cep="50000000",
                endereco="Rua X", numero=10, complemento=None, bairro="Boa Vista",
                municipio="Recife", estado="PE", email="a@acme.com",
                telefones=None, celular="81999990000", whatsapp=None)
    base.update(kw)
    return SimpleNamespace(**base)


def _empresa(**kw):
    base = dict(id=9, nome="ACME Filial", cgc="36312056000552", cpf=None, cep="29680000",
                endereco="BR 101", numero="S/N", complemento="KM 196", bairro="Zona Rural",
                municipio="Joao Neiva", estado="ES", email="f@acme.com", telefone="2733330000")
    base.update(kw)
    return SimpleNamespace(**base)


def test_dados_destinatario_cliente_prefere_telefones_e_numero_vira_texto():
    d = empresa.dados_destinatario(_cliente(telefones="8130001111"), tipo="cliente")
    assert d["tipo"] == "cliente" and d["id"] == 5
    assert d["documento"] == "08857492000148"
    assert d["numero"] == "10"
    assert d["telefone"] == "8130001111"
    assert "matriz_id" not in d


def test_dados_destinatario_cliente_sem_telefones_cai_no_celular():
    assert empresa.dados_destinatario(_cliente(), tipo="cliente")["telefone"] == "81999990000"


def test_dados_destinatario_empresa_com_matriz():
    d = empresa.dados_destinatario(_empresa(), tipo="empresa", matriz=_cliente())
    assert d["tipo"] == "empresa" and d["id"] == 9
    assert d["numero"] == "S/N"
    assert d["telefone"] == "2733330000"
    assert d["matriz_id"] == 5 and d["matriz_nome"] == "ACME"


def test_dados_destinatario_empresa_sem_matriz():
    d = empresa.dados_destinatario(_empresa(), tipo="empresa")
    assert d["matriz_id"] is None and d["matriz_nome"] is None


def test_destinatario_legado_reproduz_o_pdf_de_hoje():
    # O PDF antigo nao imprimia numero/bairro do cadastro e lia celular antes de telefones.
    d = empresa.destinatario_legado(_cliente(telefones="8130001111"), {"nome": "ACME SP", "cep": "01000000"})
    assert d["tipo"] == "cliente" and d["id"] == 5
    assert d["nome"] == "ACME SP"
    assert d["cep"] == "01000000"
    assert d["endereco"] == "Rua X"
    assert d["numero"] is None and d["bairro"] is None
    assert d["telefone"] == "81999990000"


def test_destinatario_legado_sem_cliente_usa_so_o_override():
    d = empresa.destinatario_legado(None, {"nome": "Avulso", "documento": "123.456.789-09"})
    assert d["id"] is None
    assert d["nome"] == "Avulso"
    assert d["documento"] == "12345678909"


def test_destinatario_legado_vazio():
    d = empresa.destinatario_legado(None, None)
    assert d["nome"] is None and d["documento"] is None


def test_linha_endereco():
    assert empresa.linha_endereco({"endereco": "BR 101", "numero": "S/N", "complemento": "KM 196", "bairro": "Zona Rural"}) == "BR 101, S/N KM 196 - Zona Rural"
    assert empresa.linha_endereco({"endereco": "Rua X, 10", "numero": None}) == "Rua X, 10"
    assert empresa.linha_endereco({}) == ""


def test_model_empresa_com_matriz(db_session):
    from app.models import Cliente, Empresa
    cli = Cliente(nome="ACME", cgc="08857492000148")
    db_session.add(cli); db_session.flush()
    e = Empresa(nome="ACME Filial", cgc="36312056000552", cliente=cli.id)
    db_session.add(e); db_session.flush()
    db_session.refresh(e)
    assert e.ativo is True
    assert e.matriz_rel.nome == "ACME"


def test_model_empresa_cgc_unico(db_session):
    from sqlalchemy.exc import IntegrityError
    from app.models import Empresa
    db_session.add(Empresa(nome="A", cgc="36312056000552")); db_session.flush()
    db_session.add(Empresa(nome="B", cgc="36312056000552"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_model_empresa_exige_exatamente_um_documento(db_session):
    from sqlalchemy.exc import IntegrityError
    from app.models import Empresa
    db_session.add(Empresa(nome="Sem documento"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_model_proposta_aponta_para_empresa(db_session):
    from app.models import Empresa, Proposta
    e = Empresa(nome="Filial", cpf="12345678909")
    db_session.add(e); db_session.flush()
    p = Proposta(numero=1, empresa=e.id, destinatario={"tipo": "empresa", "id": e.id})
    db_session.add(p); db_session.flush(); db_session.refresh(p)
    assert p.empresa_rel.nome == "Filial"
    assert p.destinatario["tipo"] == "empresa"
