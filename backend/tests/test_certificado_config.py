from datetime import date

from app.core.certificado_config import obter_config, padrao_vigente, parametros_de
from app.models import CertificadoPadrao


def test_config_e_singleton_e_nasce_com_os_valores_da_planilha(db_session):
    c1 = obter_config(db_session)
    assert float(c1.valor_referencia) == 0.1
    assert float(c1.limite_minimo) == 0.15
    assert float(c1.limite_maximo) == 0.19
    assert float(c1.resolucao_instrumento) == 0.1
    assert float(c1.incerteza_padrao_temp) == 0.052
    assert float(c1.fator_k) == 2
    assert c1.tecnico_nome == "Walbert Santos"

    # segunda chamada devolve a MESMA linha — nao cria outra
    c2 = obter_config(db_session)
    assert c2.id == c1.id
    assert db_session.query(type(c1)).count() == 1


def test_parametros_de_converte_decimal_para_float(db_session):
    p = parametros_de(obter_config(db_session))
    assert p.valor_referencia == 0.1
    assert p.resolucao_instrumento == 0.1
    assert p.incerteza_padrao_temp == 0.052
    assert p.resolucao_pressao is None
    assert p.fator_k == 2.0


def _padrao(db, **kw):
    dados = dict(
        numero_cilindro="CC747704", numero_certificado="202231419",
        concentracao=100.1, incerteza_concentracao=2.0, unidade="µmol/mol",
        vigencia_inicio=date(2025, 1, 1), vigencia_fim=None, ativo=True,
    )
    dados.update(kw)
    obj = CertificadoPadrao(**dados)
    db.add(obj)
    db.commit()
    return obj


def test_padrao_vigente_resolve_pela_data(db_session):
    antigo = _padrao(db_session, numero_cilindro="ANTIGO",
                     vigencia_inicio=date(2024, 1, 1), vigencia_fim=date(2024, 12, 31))
    atual = _padrao(db_session, vigencia_inicio=date(2025, 1, 1), vigencia_fim=None)

    assert padrao_vigente(db_session, date(2024, 6, 1)).id == antigo.id
    assert padrao_vigente(db_session, date(2026, 6, 1)).id == atual.id


def test_padrao_vigente_sem_correspondencia_devolve_none(db_session):
    # OS antiga, anterior a qualquer cilindro cadastrado: nao inventa padrao
    _padrao(db_session, vigencia_inicio=date(2025, 1, 1))
    assert padrao_vigente(db_session, date(2020, 1, 1)) is None
    assert padrao_vigente(db_session, None) is None


def test_padrao_inativo_e_ignorado(db_session):
    _padrao(db_session, ativo=False)
    assert padrao_vigente(db_session, date(2026, 1, 1)) is None


def test_ordem_tem_as_colunas_novas(db_session):
    from app.models import Ordem
    assert hasattr(Ordem, "calib_teste4")
    assert hasattr(Ordem, "calib_teste5")
    assert hasattr(Ordem, "padrao_id")


def test_equipamento_cliente_tem_as_colunas_novas():
    from app.models import EquipamentoCliente
    assert hasattr(EquipamentoCliente, "calib_teste4")
    assert hasattr(EquipamentoCliente, "calib_teste5")
