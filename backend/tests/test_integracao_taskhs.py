"""Endpoint inbound `POST /integracao/taskhs/caixas/{id}/financeiro`.

Chamado pela automacao do TaskHS quando o card entra na lista do Financeiro (205).
So vale para caixa com PHOEBUS dentro: sair da fase 6 grava `aceite`, e na caixa
normal esse aval vem do "Ganho" da proposta no GrowthHS — deixar o TaskHS gravar
seria forjar aprovacao comercial.

Usa o `client` do conftest (X-API-Key, nao JWT).
"""
import pytest

from app.core.config import settings
from app.models import Caixa, Cliente, Equipamento, EquipamentoCliente, LogOS, Ordem

CHAVE = "segredo-taskhs-123"


@pytest.fixture(autouse=True)
def _fases(fases_seed):
    """`caixas.fase` e `ordens.fase` sao FK para `fases` — sem o seed o INSERT morre."""


@pytest.fixture(autouse=True)
def _chave(monkeypatch):
    monkeypatch.setattr(settings, "TASKHS_INBOUND_API_KEY", CHAVE)


def _caixa(db, *, catalogos, fase=6):
    """Caixa na fase informada, uma OS por item de `catalogos`.

    Item `None` cria a OS SEM equipamento vinculado (`equipamento_catalogo` devolve
    None) — e' o caso da caixa "normal" do conftest, e nao a mesma coisa que uma
    lista vazia, que criaria caixa sem OS nenhuma.
    """
    cli = Cliente(nome="Cliente TaskHS")
    db.add(cli); db.flush()
    cx = Caixa(obs="Caixa taskhs", fase=fase)
    db.add(cx); db.flush()
    ids = []
    for cat in catalogos:
        ec_id = None
        if cat is not None:
            eq = db.query(Equipamento).filter(Equipamento.id == cat).one_or_none()
            if eq is None:
                eq = Equipamento(id=cat, descricao=f"Equipamento {cat}")
                db.add(eq); db.flush()
            ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id,
                                    serie=f"S-{cat}-{len(ids)}")
            db.add(ec); db.flush()
            ec_id = ec.id
        o = Ordem(cliente=cli.id, equipamento_cliente=ec_id, fase=fase,
                  situacao="E", caixa=cx.id)
        db.add(o); db.flush()
        ids.append(o.id)
    db.commit(); db.refresh(cx)
    return cx.id, ids


def _chamar(client, caixa_id, *, chave=CHAVE, body=None):
    return client.post(f"/integracao/taskhs/caixas/{caixa_id}/financeiro",
                       json=body if body is not None else {"card_id": 2018},
                       headers={"X-API-Key": chave})


PAR = [settings.EQUIPAMENTO_PHOEBUS_ID, settings.EQUIPAMENTO_MODULO_ID]


def test_phoebus_com_modulo_avanca_para_financeiro(client, db_session):
    cx_id, os_ids = _caixa(db_session, catalogos=PAR)
    r = _chamar(client, cx_id)
    assert r.status_code == 200
    assert r.json() == {"movida": True, "caixa_id": cx_id, "fase": 10}

    db_session.expire_all()
    assert db_session.get(Caixa, cx_id).fase == 10
    assert all(db_session.get(Ordem, i).fase == 10 for i in os_ids)


def test_so_phoebus_avanca(client, db_session):
    cx_id, _ = _caixa(db_session, catalogos=[settings.EQUIPAMENTO_PHOEBUS_ID])
    assert _chamar(client, cx_id).json()["movida"] is True


def test_phoebus_com_aparelho_comum_grava_aceite_no_aparelho_comum_por_decisao(client, db_session):
    """DECISAO, nao descuido (caixa real de producao: 1041, 1 Phoebus + 2
    Iblow10 PRO, aceite=False nas 3 OS em 18/09/2026). A trava de `_tem_phoebus`
    e' `any`: a caixa com Phoebus e um aparelho comum avanca e o fan-out de
    `executar_avanco_caixa` grava `aceite=True` tambem na OS do aparelho comum,
    que normalmente so recebe aval pelo "Ganho" do GrowthHS.

    E' aceitavel porque essa caixa NAO TEM card no GrowthHS (board comercial,
    Phoebus nao tem proposta la) — nao existe caminho de "Ganho" que traria o
    aceite por outra via. Barrar aqui travaria a caixa para sempre."""
    cx_id, os_ids = _caixa(db_session, catalogos=[settings.EQUIPAMENTO_PHOEBUS_ID, 1])
    r = _chamar(client, cx_id)
    assert r.status_code == 200
    assert r.json()["movida"] is True

    db_session.expire_all()
    for i in os_ids:
        o = db_session.get(Ordem, i)
        assert o.aceite is True
        assert o.data_aceite is not None


def test_caixa_normal_recusa_409_e_nao_ganha_aceite(client, db_session):
    """A trava de escopo. Caixa sem Phoebus tem o "Ganho" do GrowthHS como fonte do
    aceite; avancar por aqui gravaria um aval comercial que ninguem deu."""
    cx_id, os_ids = _caixa(db_session, catalogos=[1])
    r = _chamar(client, cx_id)
    assert r.status_code == 409
    assert "phoebus" in r.json()["detail"].lower()

    db_session.expire_all()
    assert db_session.get(Caixa, cx_id).fase == 6
    o = db_session.get(Ordem, os_ids[0])
    assert o.aceite is not True
    assert o.data_aceite is None


def test_caixa_com_os_sem_equipamento_recusa_409(client, db_session):
    """OS sem equipamento vinculado nao tem Phoebus — `equipamento_catalogo` devolve
    None, e None nao pode passar pela trava por omissao. E' a forma das caixas da
    fixture `caixa_posvendas` do conftest."""
    cx_id, _ = _caixa(db_session, catalogos=[None, None])
    assert _chamar(client, cx_id).status_code == 409


def test_caixa_100_por_cento_modulo_recusa_409(client, db_session):
    """Essa nao tem card no board (fica fora do espelhamento), entao nao deveria
    chegar aqui. Se chegar, recusa."""
    cx_id, _ = _caixa(db_session, catalogos=[settings.EQUIPAMENTO_MODULO_ID])
    assert _chamar(client, cx_id).status_code == 409


def test_segunda_chamada_e_no_op_nao_erro(client, db_session):
    """O laco card -> caixa -> card: avancar move o card para a lista 205, o que
    dispara a automacao de volta. E' aqui que a corrente morre."""
    cx_id, _ = _caixa(db_session, catalogos=PAR)
    assert _chamar(client, cx_id).json()["movida"] is True
    r = _chamar(client, cx_id)
    assert r.status_code == 200
    assert r.json() == {"movida": False, "caixa_id": cx_id, "fase": 10}


def test_caixa_em_laboratorio_devolve_409(client, db_session):
    cx_id, _ = _caixa(db_session, catalogos=PAR, fase=5)
    assert _chamar(client, cx_id).status_code == 409


def test_caixa_arquivada_devolve_409_com_mensagem_de_fase(client, db_session):
    """Caixa arquivada (cancelada) tem `fase=None` na caixa E nas OS —
    `_ordens_ativas` devolve lista vazia, e a trava de Phoebus daria "sem
    Phoebus" para uma caixa que na verdade foi cancelada. A mensagem tem que ser
    a de fase errada, nao a de Phoebus (ACHADO 2 da revisao)."""
    cx_id, _ = _caixa(db_session, catalogos=PAR, fase=None)
    r = _chamar(client, cx_id)
    assert r.status_code == 409
    assert "phoebus" not in r.json()["detail"].lower()
    assert r.json()["detail"] == "caixa nao esta em Pos-Vendas"


def test_caixa_inexistente_devolve_404(client):
    assert _chamar(client, 999999).status_code == 404


def test_grava_obs_no_log_da_os(client, db_session):
    cx_id, os_ids = _caixa(db_session, catalogos=PAR)
    _chamar(client, cx_id, body={"card_id": 2018, "observacao": "card 2018"})

    textos = [l.texto for l in db_session.query(LogOS).filter(LogOS.os == os_ids[0]).all()]
    assert any("via TaskHS" in (t or "") for t in textos)
    assert any("card 2018" in (t or "") for t in textos)


def test_chave_errada_devolve_401(client, db_session):
    cx_id, _ = _caixa(db_session, catalogos=PAR)
    assert _chamar(client, cx_id, chave="errada").status_code == 401


def test_header_ausente_devolve_401(client, db_session):
    cx_id, _ = _caixa(db_session, catalogos=PAR)
    r = client.post(f"/integracao/taskhs/caixas/{cx_id}/financeiro", json={})
    assert r.status_code == 401


def test_header_nao_ascii_devolve_401_e_nao_500(client, db_session):
    """Starlette decodifica header como latin-1; `compare_digest` levanta TypeError
    com caractere nao-ASCII. Sem o guard isso vira 500.

    Envia o header como bytes latin-1 (nao str): o proprio httpx do TestClient
    forca ascii num valor str antes de sair, entao "chave-com-acento-ç" como str
    nunca chegaria ao servidor — mesmo ajuste de
    test_integracao_growthhs_auth.py::test_header_nao_ascii_retorna_401_e_nao_500.
    Escopado a este teste (nao ao helper `_chamar`) para o contorno ficar visivel
    exatamente onde importa.
    """
    cx_id, _ = _caixa(db_session, catalogos=PAR)
    r = client.post(f"/integracao/taskhs/caixas/{cx_id}/financeiro",
                    json={"card_id": 2018},
                    headers={"X-API-Key": "chave-com-acento-ç".encode("latin-1")})
    assert r.status_code == 401


def test_integracao_desligada_devolve_503(client, db_session, monkeypatch):
    cx_id, _ = _caixa(db_session, catalogos=PAR)
    monkeypatch.setattr(settings, "TASKHS_INBOUND_API_KEY", "")
    assert _chamar(client, cx_id).status_code == 503
