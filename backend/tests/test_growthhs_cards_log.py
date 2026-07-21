from types import SimpleNamespace

from app.api import growthhs_cards
from app.core.config import settings


class _BG:
    def add_task(self, *a, **k):
        pass


def test_pulo_sem_equipamento_loga(monkeypatch):
    monkeypatch.setattr(settings, "HSGROWTH_BASE_URL", "https://growth.test")
    monkeypatch.setattr(settings, "HSGROWTH_API_KEY", "k")
    chamadas = []
    monkeypatch.setattr(growthhs_cards, "registrar_log_integracao",
                        lambda **kw: chamadas.append(kw))
    ordem = SimpleNamespace(id=999, equipamento_rel=None)
    growthhs_cards.agendar_card_os(db=None, background_tasks=_BG(), ordem=ordem)
    assert chamadas and chamadas[0]["status"] == "pulado"
    assert chamadas[0]["motivo"] == "sem_equipamento"
    assert chamadas[0]["referencia_os"] == 999
