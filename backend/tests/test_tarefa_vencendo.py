import asyncio
from datetime import date

import pytest

from app.core.config import settings
from app.tarefas import vencendo


@pytest.fixture(autouse=True)
def _job_ligado(monkeypatch):
    monkeypatch.setattr(settings, "JOB_VENCENDO_ATIVO", True)
    monkeypatch.setattr(settings, "JOB_VENCENDO_HORA", 8)


# O sleep entra por PARAMETRO, nunca por monkeypatch de `asyncio.sleep`:
# `vencendo.asyncio` e' o modulo global, entao troca-lo afeta o event loop do proprio
# teste. Tentar isso custou um RecursionError e uma suite travada.
def _dormir_na_hora(registro):
    async def dormir(segundos):
        registro.append(segundos)
    return dormir


def test_nasce_desligado_por_padrao():
    """O container de DESENVOLVIMENTO aponta para o banco de producao com a chave
    real. Se o agendador ligasse por padrao, a maquina de qualquer dev passaria a
    criar cards sozinha. Ligar e' decisao explicita de quem faz o deploy."""
    campo = type(settings).model_fields["JOB_VENCENDO_ATIVO"]
    assert campo.default is False


def test_iniciar_nao_cria_task_quando_desligado(monkeypatch):
    monkeypatch.setattr(settings, "JOB_VENCENDO_ATIVO", False)

    async def cenario():
        assert vencendo.iniciar() is None

    asyncio.run(cenario())


def test_iniciar_cria_task_quando_ligado():
    async def cenario():
        task = vencendo.iniciar(ciclos=0)
        assert task is not None
        await task

    asyncio.run(cenario())


def test_roda_o_job_no_horario(monkeypatch):
    """Um ciclo: dorme o que o calculo mandar e entao roda o job."""
    dormiu, rodou = [], []
    monkeypatch.setattr(vencendo, "_rodar_job", lambda: rodou.append(True))

    asyncio.run(vencendo.loop_mensal(ciclos=1, dormir=_dormir_na_hora(dormiu)))

    assert len(dormiu) == 1 and dormiu[0] > 0     # esperou ate o horario
    assert rodou == [True]


def test_falha_no_job_nao_mata_o_loop(monkeypatch):
    """Se o GrowthHS cair, o worker precisa sobreviver e tentar de novo amanha —
    uma excecao aqui nao pode derrubar a task nem a API."""
    rodadas = []

    def as_vezes_falha():
        rodadas.append(len(rodadas))
        if len(rodadas) == 1:
            raise RuntimeError("GrowthHS fora do ar")

    monkeypatch.setattr(vencendo, "_rodar_job", as_vezes_falha)

    asyncio.run(vencendo.loop_mensal(ciclos=2, dormir=_dormir_na_hora([])))

    assert len(rodadas) == 2                       # seguiu depois da falha


def test_cancelamento_encerra_limpo():
    """No shutdown a task e' cancelada; isso nao pode virar erro no log."""
    async def dormir_muito(_segundos):
        await asyncio.sleep(3600)

    async def cenario():
        task = vencendo.iniciar(dormir=dormir_muito)
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cenario())


def test_rodar_job_usa_o_mes_corrente_e_o_seguinte(monkeypatch):
    """O worker precisa chamar o MESMO processar() do script — nada de uma segunda
    copia da regra de selecao (o projeto ja se queimou com logica duplicada)."""
    chamadas = {}

    class FakeSession:
        def close(self):
            chamadas["fechou"] = True

    monkeypatch.setattr(vencendo, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(vencendo, "processar",
                        lambda db, **kw: chamadas.update(kw) or
                        {"clientes": 2, "aparelhos": 5, "criados": 2, "existentes": 0,
                         "falhas": 0, "pendencias": [], "excluidos": []})

    vencendo._rodar_job()

    hoje = date.today()
    corrente = hoje.replace(day=1)
    seguinte = (corrente.replace(year=corrente.year + 1, month=1)
                if corrente.month == 12 else corrente.replace(month=corrente.month + 1))
    assert chamadas["competencias"] == [corrente, seguinte]
    assert chamadas["enviar"] is True
    assert chamadas["fechou"] is True


def test_rodar_job_fecha_a_sessao_mesmo_com_erro(monkeypatch):
    """Vazar conexao a cada falha diaria esgotaria o pool com o tempo."""
    fechou = []

    class FakeSession:
        def close(self):
            fechou.append(True)

    monkeypatch.setattr(vencendo, "SessionLocal", lambda: FakeSession())

    def explode(db, **kw):
        raise RuntimeError("banco fora")

    monkeypatch.setattr(vencendo, "processar", explode)

    with pytest.raises(RuntimeError):
        vencendo._rodar_job()

    assert fechou == [True]


def test_logs_do_app_chegam_em_nivel_info():
    """Guarda contra regressao silenciosa: o root logger fica em WARNING, entao sem
    a configuracao do main o `logger.info` do worker — e o relatorio de falhas —
    seriam descartados, e ligar o job em producao nao mostraria nada no log."""
    import logging

    import app.main  # noqa: F401 — importar aplica a configuracao

    assert logging.getLogger("app.tarefas.vencendo").isEnabledFor(logging.INFO)
    assert logging.getLogger("app.scripts.enviar_vencendo_growthhs").isEnabledFor(logging.INFO)
