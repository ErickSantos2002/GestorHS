"""As tabelas de manutencao. O conftest cria o schema pelo metadata, entao um
modelo que nao esteja em app.models nao existiria aqui."""
import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Manutencao, ManutencaoServico, ManutencaoItem


def _os(db, os_base, fase=5):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"],
              fase=fase, tipo_servico="M", situacao="E")
    db.add(o); db.commit(); db.refresh(o)
    return o


def test_grava_manutencao_com_itens(db_session, os_base, fases_seed):
    from datetime import date
    o = _os(db_session, os_base)
    servico = ManutencaoServico(descricao="Troca da placa mãe", resumo_padrao="Placa substituída.")
    db_session.add(servico); db_session.flush()
    m = Manutencao(os=o.id, numero="HF00715", data_manutencao=date(2026, 8, 21),
                   resumo="Placa substituída.", criado_por="Tecnico")
    db_session.add(m); db_session.flush()
    db_session.add(ManutencaoItem(manutencao=m.id, servico=servico.id, ordem=0))
    db_session.commit(); db_session.refresh(m)

    assert m.numero == "HF00715"
    assert len(m.itens) == 1
    assert m.itens[0].servico_rel.descricao == "Troca da placa mãe"


def test_uma_manutencao_por_os(db_session, os_base, fases_seed):
    """Espelha a unicidade (os, tipo) de os_certificados: um relatorio por OS."""
    from datetime import date
    o = _os(db_session, os_base)
    db_session.add(Manutencao(os=o.id, numero="A", data_manutencao=date(2026, 8, 21)))
    db_session.commit()
    db_session.add(Manutencao(os=o.id, numero="B", data_manutencao=date(2026, 8, 21)))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_servico_com_descricao_repetida_e_recusado(db_session):
    db_session.add(ManutencaoServico(descricao="Troca da bateria", resumo_padrao="x"))
    db_session.commit()
    db_session.add(ManutencaoServico(descricao="Troca da bateria", resumo_padrao="y"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_servico_nasce_ativo(db_session):
    s = ManutencaoServico(descricao="Troca do bocal", resumo_padrao="x")
    db_session.add(s); db_session.commit(); db_session.refresh(s)
    assert s.ativo is True


def test_mesmo_servico_duas_vezes_na_mesma_manutencao_e_recusado(db_session, os_base, fases_seed):
    from datetime import date
    o = _os(db_session, os_base)
    s = ManutencaoServico(descricao="Troca do botão", resumo_padrao="x")
    db_session.add(s); db_session.flush()
    m = Manutencao(os=o.id, numero="A", data_manutencao=date(2026, 8, 21))
    db_session.add(m); db_session.flush()
    db_session.add(ManutencaoItem(manutencao=m.id, servico=s.id, ordem=0))
    db_session.commit()
    db_session.add(ManutencaoItem(manutencao=m.id, servico=s.id, ordem=1))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
