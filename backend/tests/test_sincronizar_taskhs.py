import pytest

from app.core.config import settings
from app.integrations import taskhs_client
from app.scripts import sincronizar_taskhs


def _abrir_os(db, os_base, fase):
    from app.models import Ordem
    o = Ordem(cliente=os_base["cliente"], equipamento_cliente=os_base["equipamento_cliente"],
              fase=fase, tipo_servico="C", situacao="E")
    db.add(o); db.commit(); db.refresh(o)
    return o


def test_sincronizar_envia_so_fases_4_a_8(db_session, os_base, fases_seed, monkeypatch):
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "http://t/api")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "k")
    _abrir_os(db_session, os_base, 4)
    _abrir_os(db_session, os_base, 8)
    _abrir_os(db_session, os_base, 9)  # cancelada: ignorada
    _abrir_os(db_session, os_base, 10)
    enviados = []
    monkeypatch.setattr(taskhs_client, "espelhar_os",
                        lambda ordem, *, lista, arquivado=False: enviados.append((ordem.fase, lista)))
    enviadas, total = sincronizar_taskhs.sincronizar(db_session)
    assert enviadas == 3
    assert total == 3
    fases = sorted(f for f, _ in enviados)
    assert fases == [4, 8, 10]


def test_sincronizar_desligada_levanta(db_session, monkeypatch):
    monkeypatch.setattr(settings, "TASKHS_BASE_URL", "")
    monkeypatch.setattr(settings, "TASKHS_API_KEY", "")
    with pytest.raises(RuntimeError):
        sincronizar_taskhs.sincronizar(db_session)
