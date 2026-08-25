"""Sync cirurgico de cards de CAIXA no TaskHS.

Existe porque o encerramento em lote das caixas da carga retroativa de Ganho
(25/08/2026) foi feito por SQL, fora do fluxo da API — os cards ficaram parados na
lista de Financeiro em vez de ir para 📮 Correios. O backfill geral
(sincronizar_taskhs) mexeria em centenas de OS, inclusive as que ficaram em drift
de proposito em julho; este roda so nas caixas indicadas.
"""
import pytest

from app.core.config import settings
from app.scripts import sincronizar_taskhs_caixas


@pytest.fixture()
def caixas_fase8(db_session, os_base, fases_seed):
    """Duas caixas em Finalizada(8), cada uma com uma OS."""
    from app.models import Caixa, Ordem
    ids = []
    for _ in range(2):
        cx = Caixa(obs="lote", fase=8)
        db_session.add(cx); db_session.flush()
        db_session.add(Ordem(cliente=os_base["cliente"],
                             equipamento_cliente=os_base["equipamento_cliente"],
                             fase=8, tipo_servico="C", situacao="F", caixa=cx.id))
        ids.append(cx.id)
    db_session.commit()
    return ids


def _ligar(monkeypatch):
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "http://t/api")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "k")


def test_manda_cada_caixa_para_a_lista_da_sua_fase(db_session, caixas_fase8, monkeypatch):
    from app.api import espelhamento
    _ligar(monkeypatch)
    enviados = []
    monkeypatch.setattr(espelhamento, "espelhar_caixa_sync",
                        lambda db, caixa, *, list_id, arquivado=False: (
                            enviados.append((caixa.id, list_id)) or True))

    enviadas, total = sincronizar_taskhs_caixas.sincronizar(db_session, caixas_fase8)

    assert (enviadas, total) == (2, 2)
    # Fase 8 -> 📮 Correios (210). E' o ponto todo do script.
    assert {lid for _, lid in enviados} == {210}
    assert sorted(c for c, _ in enviados) == sorted(caixas_fase8)


def test_ignora_caixa_inexistente(db_session, caixas_fase8, monkeypatch):
    from app.api import espelhamento
    _ligar(monkeypatch)
    monkeypatch.setattr(espelhamento, "espelhar_caixa_sync",
                        lambda db, caixa, *, list_id, arquivado=False: True)

    enviadas, total = sincronizar_taskhs_caixas.sincronizar(db_session, caixas_fase8 + [999999])

    assert (enviadas, total) == (2, 2)


def test_caixa_sem_fase_mapeada_nao_e_enviada(db_session, os_base, fases_seed, monkeypatch):
    """Caixa encerrada (fase NULL) nao tem lista no board — pular, nao explodir."""
    from app.models import Caixa
    from app.api import espelhamento
    _ligar(monkeypatch)
    cx = Caixa(obs="encerrada", fase=None)
    db_session.add(cx); db_session.commit(); db_session.refresh(cx)
    monkeypatch.setattr(espelhamento, "espelhar_caixa_sync",
                        lambda db, caixa, *, list_id, arquivado=False: True)

    enviadas, total = sincronizar_taskhs_caixas.sincronizar(db_session, [cx.id])

    assert (enviadas, total) == (0, 1)


def test_integracao_desligada_levanta(db_session, monkeypatch):
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "")
    with pytest.raises(RuntimeError):
        sincronizar_taskhs_caixas.sincronizar(db_session, [1])
