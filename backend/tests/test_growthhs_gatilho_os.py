"""Gatilho do card GrowthHS ao sair do laboratorio (5->6).

Cobertura via API do avanco de fase (5->6) foi removida junto com o endpoint
per-OS `/ordens/{id}/avancar` (a OS agora anda pela caixa — ver
`test_caixa_avancar.py`). O que resta aqui e' o teste de unidade de
`agendar_card_os` que nao depende do endpoint de avanco per-OS.
"""


def test_agendar_card_os_sem_equipamento_nao_agenda_e_loga_warning_sem_stacktrace(db_session, monkeypatch, caplog):
    """Fix 4: `ordem.equipamento_cliente` e' nullable — uma OS sem equipamento e' um
    dado benigno, nao uma excecao. Antes caia no `except` generico e virava log de
    erro com stack trace; agora e' guardado explicitamente (warning, sem card)."""
    import logging
    from types import SimpleNamespace
    from app.core.config import settings
    from app.api.growthhs_cards import agendar_card_os
    monkeypatch.setattr(settings, "HSGROWTH_BASE_URL", "https://growth.test")
    monkeypatch.setattr(settings, "HSGROWTH_API_KEY", "chave-123")

    ordem = SimpleNamespace(id=777, equipamento_rel=None, equipamento_descricao=None)

    class _BackgroundTasksFake:
        def __init__(self):
            self.chamadas = []

        def add_task(self, func, *a, **k):
            self.chamadas.append((func, a, k))

    bt = _BackgroundTasksFake()
    with caplog.at_level(logging.WARNING, logger="app.api.growthhs_cards"):
        agendar_card_os(db_session, bt, ordem)

    assert bt.chamadas == []
    assert any(r.levelno == logging.WARNING and "777" in r.getMessage() for r in caplog.records)
    assert not any(r.levelno >= logging.ERROR for r in caplog.records)
