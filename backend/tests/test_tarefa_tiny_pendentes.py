import asyncio

import pytest

from app.core.config import settings
from app.models import Empresa
from app.tarefas import tiny_pendentes

CNPJ = "36312056000552"


@pytest.fixture(autouse=True)
def _job_ligado(monkeypatch):
    monkeypatch.setattr(settings, "JOB_TINY_ATIVO", True)
    monkeypatch.setattr(settings, "TINY_TOKEN", "tok-123")


def _empresa(db, documento, **kw):
    e = Empresa(nome="Filial", cgc=documento, **kw)
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


# O sleep entra por PARAMETRO, nunca por monkeypatch de `asyncio.sleep` — mesmo
# motivo documentado em test_tarefa_vencendo.py.
def _dormir_na_hora(registro):
    async def dormir(segundos):
        registro.append(segundos)
    return dormir


def test_nasce_desligado_por_padrao():
    """Esta maquina aponta para o banco de PRODUCAO com o token real do Tiny, que
    nao tem ambiente de teste. Ligar sozinho faria qualquer dev espelhar empresa
    de verdade no ERP da empresa."""
    assert type(settings).model_fields["JOB_TINY_ATIVO"].default is False


def test_iniciar_nao_cria_task_quando_desligado(monkeypatch):
    monkeypatch.setattr(settings, "JOB_TINY_ATIVO", False)

    async def cenario():
        assert tiny_pendentes.iniciar() is None

    asyncio.run(cenario())


def test_iniciar_nao_cria_task_sem_token(monkeypatch):
    """Job ligado mas integracao sem token: a varredura so gastaria banco para
    descobrir que `sincronizar_empresa` e' no-op."""
    monkeypatch.setattr(settings, "TINY_TOKEN", "")

    async def cenario():
        assert tiny_pendentes.iniciar() is None

    asyncio.run(cenario())


def test_pendentes_pega_so_as_que_pedem_nova_tentativa(db_session):
    """`pendente` e' "falhou por algo transitorio, tente de novo". `erro` e' recusa
    do Tiny que nao muda sozinha — repetir a cada 10 min gastaria chamada para
    sempre contra uma conta limitada a 20 por minuto."""
    alvo = _empresa(db_session, CNPJ, tiny_status="pendente")
    _empresa(db_session, "11222333000181", tiny_status="erro")
    _empresa(db_session, "08857492000148", tiny_status="enviada")
    _empresa(db_session, "05571228000150", tiny_status=None)
    _empresa(db_session, "99988877000166", tiny_status="pendente", ativo=False)

    assert [e.id for e in tiny_pendentes.pendentes(db_session, limite=10)] == [alvo.id]


def test_pendentes_respeita_o_limite_da_volta(db_session):
    """Teto por volta: cada empresa gasta 2 chamadas e a conta permite 20 por
    minuto — uma fila grande nao pode estourar o limite de uma vez."""
    for doc in ("36312056000552", "11222333000181", "08857492000148"):
        _empresa(db_session, doc, tiny_status="pendente")

    assert len(tiny_pendentes.pendentes(db_session, limite=2)) == 2


def test_rodar_job_sincroniza_cada_pendente(db_session, monkeypatch):
    chamadas = []
    monkeypatch.setattr(tiny_pendentes, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(tiny_pendentes.tiny_client, "sincronizar_empresa",
                        lambda eid, **kw: chamadas.append(eid))

    a = _empresa(db_session, CNPJ, tiny_status="pendente")
    b = _empresa(db_session, "11222333000181", tiny_status="pendente")

    resumo = tiny_pendentes._rodar_job(pausa=0)

    assert sorted(chamadas) == sorted([a.id, b.id])
    assert resumo["tentadas"] == 2


def test_base_sem_pendencia_nao_fala_com_o_tiny(db_session, monkeypatch):
    """"Se nada tiver pendente o cron so ignora": nenhuma chamada, nenhum log."""
    chamadas = []
    monkeypatch.setattr(tiny_pendentes, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(tiny_pendentes.tiny_client, "sincronizar_empresa",
                        lambda eid, **kw: chamadas.append(eid))
    _empresa(db_session, CNPJ, tiny_status="enviada")

    resumo = tiny_pendentes._rodar_job(pausa=0)

    assert chamadas == [] and resumo["tentadas"] == 0


def test_loop_dorme_o_intervalo_e_roda(monkeypatch):
    dormiu, rodou = [], []
    monkeypatch.setattr(settings, "JOB_TINY_INTERVALO_MIN", 10)
    monkeypatch.setattr(tiny_pendentes, "_rodar_job", lambda: rodou.append(True))

    asyncio.run(tiny_pendentes.loop(ciclos=1, dormir=_dormir_na_hora(dormiu)))

    assert dormiu == [600] and rodou == [True]


def test_falha_no_job_nao_mata_o_loop(monkeypatch):
    """Se o Tiny cair, o worker precisa sobreviver e tentar de novo em 10 min —
    uma excecao aqui nao pode derrubar a task nem sumir com o agendamento."""
    rodadas = []

    def as_vezes_falha():
        rodadas.append(len(rodadas))
        if len(rodadas) == 1:
            raise RuntimeError("Tiny fora do ar")

    monkeypatch.setattr(tiny_pendentes, "_rodar_job", as_vezes_falha)

    asyncio.run(tiny_pendentes.loop(ciclos=2, dormir=_dormir_na_hora([])))

    assert len(rodadas) == 2


def test_cancelamento_encerra_limpo():
    """No shutdown a task e' cancelada; isso nao pode virar erro no log."""
    async def dormir_muito(_segundos):
        await asyncio.sleep(3600)

    async def cenario():
        task = tiny_pendentes.iniciar(dormir=dormir_muito)
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cenario())


def test_rodar_job_fecha_a_sessao_mesmo_com_erro(monkeypatch):
    """Vazar conexao a cada volta esgotaria o pool em algumas horas."""
    fechou = []

    class FakeSession:
        def close(self):
            fechou.append(True)

    monkeypatch.setattr(tiny_pendentes, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(tiny_pendentes, "pendentes",
                        lambda db, limite: (_ for _ in ()).throw(RuntimeError("banco fora")))

    with pytest.raises(RuntimeError):
        tiny_pendentes._rodar_job(pausa=0)

    assert fechou == [True]


def test_logs_do_worker_chegam_em_nivel_info():
    """O root logger fica em WARNING: sem a configuracao do main, ligar o job em
    producao nao mostraria nada no log."""
    import logging

    import app.main  # noqa: F401 — importar aplica a configuracao

    assert logging.getLogger("app.tarefas.tiny_pendentes").isEnabledFor(logging.INFO)


def test_lifespan_sobe_o_worker_junto_com_a_api(monkeypatch):
    """O worker so serve se alguem o pendurar no lifespan. Sem esta guarda, remover
    a linha do main passaria pela suite inteira e o job simplesmente nao existiria
    em producao — sem erro, sem log, sem nada."""
    import app.main as main

    subiram = []

    class FakeTask:
        def cancel(self):
            pass

        def __await__(self):
            async def nada():
                return None
            return nada().__await__()

    monkeypatch.setattr(main.vencendo, "iniciar", lambda: None)
    monkeypatch.setattr(main.tiny_pendentes, "iniciar",
                        lambda: (subiram.append("tiny"), FakeTask())[1])

    async def cenario():
        async with main.lifespan(main.app):
            pass

    asyncio.run(cenario())

    assert subiram == ["tiny"]
