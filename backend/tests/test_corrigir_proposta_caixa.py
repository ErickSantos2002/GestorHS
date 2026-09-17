"""O script reaponta `caixas.numero_proposta` — a conferencia dele e' a rede que
faltou no inbound do Ganho. Proposta de OUTRO cliente nao pode passar: foi
exatamente isso que pos a proposta 232 (MARINGA) na caixa 979 (UNIVALE).
"""
import pytest

from app.scripts.corrigir_proposta_caixa import clientes_da_caixa, conferir


@pytest.fixture
def caixa_com_os(db_session):
    from app.models import Caixa, Cliente, Fase, Ordem
    if db_session.query(Fase).filter(Fase.id == 7).first() is None:
        db_session.add(Fase(id=7, descricao="Preparando Retorno", cor="0ea5e9"))
        db_session.flush()
    univale = Cliente(nome="UNIVALE TRANSPORTES LTDA")
    maringa = Cliente(nome="MARINGA FERRO-LIGA S.A")
    db_session.add_all([univale, maringa])
    db_session.flush()
    cx = Caixa(fase=7, cliente_principal=univale.id, numero_proposta=232)
    db_session.add(cx)
    db_session.flush()
    db_session.add(Ordem(cliente=univale.id, situacao="E", fase=7, caixa=cx.id))
    db_session.commit()
    db_session.refresh(cx)
    return cx, univale, maringa


def _proposta(db_session, numero, cliente_id, **kw):
    from app.models import Proposta
    p = Proposta(numero=numero, cliente=cliente_id, **kw)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


def test_clientes_da_caixa_soma_principal_e_os(db_session, caixa_com_os):
    from app.models import Ordem
    cx, univale, maringa = caixa_com_os
    db_session.add(Ordem(cliente=maringa.id, situacao="E", fase=7, caixa=cx.id))
    db_session.commit()
    db_session.refresh(cx)
    assert clientes_da_caixa(cx) == {univale.id, maringa.id}


def test_proposta_do_mesmo_cliente_passa(db_session, caixa_com_os):
    cx, univale, _ = caixa_com_os
    p = _proposta(db_session, 289, univale.id)
    assert conferir(cx, p) is None


def test_proposta_de_outro_cliente_e_recusada(db_session, caixa_com_os):
    cx, _, maringa = caixa_com_os
    p = _proposta(db_session, 232, maringa.id)
    motivo = conferir(cx, p)
    assert motivo is not None
    assert "232" in motivo


def test_proposta_desabilitada_e_recusada(db_session, caixa_com_os):
    cx, univale, _ = caixa_com_os
    p = _proposta(db_session, 289, univale.id, is_deleted=True)
    assert "desabilitada" in (conferir(cx, p) or "")


def test_proposta_sem_cliente_e_recusada(db_session, caixa_com_os):
    cx, _, _ = caixa_com_os
    p = _proposta(db_session, 289, None)
    assert "sem cliente" in (conferir(cx, p) or "")


def test_caixa_sem_cliente_principal_ainda_confere_pelas_os(db_session, caixa_com_os):
    """cliente_principal so e' definido ao sair de Recebido — antes disso a unica
    fonte sao as OS, e a conferencia nao pode virar um passe livre."""
    cx, univale, maringa = caixa_com_os
    cx.cliente_principal = None
    db_session.commit()
    db_session.refresh(cx)
    assert conferir(cx, _proposta(db_session, 289, univale.id)) is None
    assert conferir(cx, _proposta(db_session, 232, maringa.id)) is not None
