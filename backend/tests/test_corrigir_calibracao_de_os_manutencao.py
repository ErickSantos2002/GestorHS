"""O script apaga/reescreve datas de calibracao do cadastro — a classificacao
dele precisa de rede. Uma OS 'M' que calibrou de fato NAO pode ser desfeita.
"""
from datetime import date, datetime, timezone

import pytest

from app.scripts.corrigir_calibracao_de_os_manutencao import (
    _calibrou_de_fato, _ultima_calibracao_real,
)


@pytest.fixture
def aparelho(db_session):
    from app.models import Cliente, Equipamento, EquipamentoCliente, Fase, Funcao
    if db_session.query(Fase).filter(Fase.id == 5).first() is None:
        f = Funcao(descricao="Laboratório"); db_session.add(f); db_session.flush()
        db_session.add(Fase(id=5, descricao="Laboratório", cor="6366f1", funcao_responsavel=f.id))
    if db_session.query(Fase).filter(Fase.id == 8).first() is None:
        db_session.add(Fase(id=8, descricao="Finalizada", cor="16a34a"))
    cli = Cliente(nome="ACME"); eq = Equipamento(descricao="Mark X")
    db_session.add_all([cli, eq]); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="S1")
    db_session.add(ec); db_session.commit(); db_session.refresh(ec)
    return ec


def _os(db_session, ec, **kw):
    from app.models import Ordem
    o = Ordem(cliente=ec.cliente, equipamento_cliente=ec.id, situacao="E",
              fase=kw.pop("fase", 5), **kw)
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    return o


def test_os_m_com_numero_de_certificado_calibrou_de_fato(db_session, aparelho):
    o = _os(db_session, aparelho, tipo_servico="M", desfecho_lab="concluido",
            calib_cert="HF02596",
            data_calibracao=datetime(2026, 8, 26, tzinfo=timezone.utc))
    assert _calibrou_de_fato(db_session, o) is True


def test_os_m_com_certificado_tipo_c_emitido_calibrou_de_fato(db_session, aparelho):
    from app.models import OSCertificado
    o = _os(db_session, aparelho, tipo_servico="M", desfecho_lab="concluido",
            data_calibracao=datetime(2026, 8, 26, tzinfo=timezone.utc))
    db_session.add(OSCertificado(os=o.id, tipo="C", html="<p/>")); db_session.commit()
    assert _calibrou_de_fato(db_session, o) is True


def test_os_m_com_apenas_relatorio_de_manutencao_e_manutencao_pura(db_session, aparelho):
    from app.models import OSCertificado
    o = _os(db_session, aparelho, tipo_servico="M", desfecho_lab="concluido",
            data_calibracao=datetime(2026, 9, 3, tzinfo=timezone.utc))
    db_session.add(OSCertificado(os=o.id, tipo="M", html="<p/>")); db_session.commit()
    assert _calibrou_de_fato(db_session, o) is False


def test_ultima_calibracao_real_ignora_a_propria_os_de_manutencao(db_session, aparelho):
    calib = _os(db_session, aparelho, tipo_servico="C", fase=8, desfecho_lab="concluido",
                data_calibracao=datetime(2026, 7, 28, tzinfo=timezone.utc),
                prox_calibragem=datetime(2027, 7, 28, tzinfo=timezone.utc))
    manut = _os(db_session, aparelho, tipo_servico="M", desfecho_lab="concluido",
                data_calibracao=datetime(2026, 9, 3, tzinfo=timezone.utc))
    assert _ultima_calibracao_real(db_session, aparelho.id, manut.id) == (
        date(2026, 7, 28), date(2027, 7, 28)
    )
    assert calib.id != manut.id


def test_ultima_calibracao_real_aceita_os_legada_sem_tipo_e_calcula_a_proxima(db_session, aparelho):
    """OS antes do campo `tipo_servico` existir sao de calibracao (regra de `tipos_para`)."""
    manut = _os(db_session, aparelho, tipo_servico="M", desfecho_lab="concluido",
                data_calibracao=datetime(2026, 8, 31, tzinfo=timezone.utc))
    _os(db_session, aparelho, tipo_servico=None, fase=8,
        data_calibracao=datetime(2026, 4, 23, tzinfo=timezone.utc), prox_calibragem=None)
    assert _ultima_calibracao_real(db_session, aparelho.id, manut.id) == (
        date(2026, 4, 23), date(2027, 4, 23)
    )


def test_aparelho_sem_nenhuma_calibracao_volta_a_nao_ter_data(db_session, aparelho):
    """A verdade e nao ter data: a que esta no cadastro so existe por causa do bug."""
    manut = _os(db_session, aparelho, tipo_servico="M", desfecho_lab="concluido",
                data_calibracao=datetime(2026, 8, 27, tzinfo=timezone.utc))
    assert _ultima_calibracao_real(db_session, aparelho.id, manut.id) == (None, None)


def test_os_de_calibracao_cancelada_nao_serve_de_referencia(db_session, aparelho):
    from app.models import Fase
    if db_session.query(Fase).filter(Fase.id == 9).first() is None:
        db_session.add(Fase(id=9, descricao="Cancelada", cor="dc2626")); db_session.commit()
    manut = _os(db_session, aparelho, tipo_servico="M", desfecho_lab="concluido",
                data_calibracao=datetime(2026, 8, 26, tzinfo=timezone.utc))
    _os(db_session, aparelho, tipo_servico="C", fase=9,
        data_calibracao=datetime(2026, 5, 28, tzinfo=timezone.utc))
    assert _ultima_calibracao_real(db_session, aparelho.id, manut.id) == (None, None)
