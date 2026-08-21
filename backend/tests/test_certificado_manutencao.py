"""Certificado de manutencao: quais tipos a OS pede e de onde vem o modelo."""
from datetime import date

import pytest

from app.core.certificado_gerar import tipos_para, modelo_para


class _OrdemFake:
    def __init__(self, tipo_servico):
        self.tipo_servico = tipo_servico


@pytest.mark.parametrize("tipo,esperado", [
    ("C", ["C"]),
    ("M", ["M"]),
    ("A", ["C", "M"]),
    (None, ["C"]),
])
def test_tipos_para_respeita_o_tipo_de_servico(tipo, esperado):
    """Manutencao pura NAO deve pedir certificado de calibracao: o tecnico
    emitiria um documento de calibracao que nao realizou."""
    assert tipos_para(_OrdemFake(tipo)) == esperado


def _equipamento(db, descricao="Bafômetro X"):
    from app.models import Equipamento
    e = Equipamento(descricao=descricao)
    db.add(e); db.commit(); db.refresh(e)
    return e


def test_modelo_de_manutencao_cai_no_generico(db_session):
    """Um modelo unico serve todos os aparelhos: os relatorios so diferem em
    marca, modelo e serie, que sao dados."""
    from app.models import CertificadoModelo
    eq = _equipamento(db_session)
    db_session.add(CertificadoModelo(equipamento=None, tipo="M", texto="<p>generico</p>"))
    db_session.commit()
    modelo = modelo_para(db_session, eq.id, "M")
    assert modelo is not None and modelo.texto == "<p>generico</p>"


def test_modelo_especifico_de_manutencao_ganha_do_generico(db_session):
    from app.models import CertificadoModelo
    eq = _equipamento(db_session)
    db_session.add(CertificadoModelo(equipamento=None, tipo="M", texto="<p>generico</p>"))
    db_session.add(CertificadoModelo(equipamento=eq.id, tipo="M", texto="<p>proprio</p>"))
    db_session.commit()
    assert modelo_para(db_session, eq.id, "M").texto == "<p>proprio</p>"


def test_calibracao_NAO_cai_no_generico(db_session):
    """Existe um modelo tipo C com equipamento nulo — o "legado" mantido em
    julho. Se o fallback valesse para C, todo aparelho sem modelo passaria a
    gerar certificado com aquele modelo de teste, sem ninguem perceber."""
    from app.models import CertificadoModelo
    eq = _equipamento(db_session)
    db_session.add(CertificadoModelo(equipamento=None, tipo="C", texto="<p>legado</p>"))
    db_session.commit()
    assert modelo_para(db_session, eq.id, "C") is None
