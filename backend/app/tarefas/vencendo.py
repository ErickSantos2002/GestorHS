"""Worker mensal: dispara o job de calibracao vencendo de dentro da propria aplicacao.

Por que aqui e nao em cron: producao sobe no Easypanel a partir do Dockerfile, onde
agendar significa instalar cron na imagem ou depender de um servico externo. Como o
backend e' um servico unico e a criacao de card e' idempotente (a chave
`{cliente_id}:{YYYY-MM}` nao muda com a data da execucao), um agendador embutido sobe
junto com o deploy, sem passo de infraestrutura — e mesmo que rodasse duas vezes, nao
criaria card duplicado.

Roda todo dia 1 as 8h (SP) sobre o mes corrente + o mes seguinte. Como o mes de tras ja
foi varrido na rodada anterior, ele volta `created: false` e na pratica so nasce card do
mes novo da ponta — a primeira rodada sobe 60 dias, as seguintes 30.

Nasce DESLIGADO (`JOB_VENCENDO_ATIVO=false`): a maquina de desenvolvimento aponta para
o banco de producao com a chave real, entao ligar tem que ser decisao explicita de quem
faz o deploy.
"""
import asyncio
import logging
from datetime import date, datetime
from typing import Optional

from app.core.agendamento import TZ_SP, segundos_ate_proxima_mensal
from app.core.config import settings
from app.models.database import SessionLocal
from app.scripts.enviar_vencendo_growthhs import competencias_padrao, processar

logger = logging.getLogger(__name__)


def _rodar_job() -> None:
    """Uma execucao. Reusa o `processar` do script — a regra de selecao mora num
    lugar so; uma segunda copia aqui divergiria com o tempo."""
    db = SessionLocal()
    try:
        r = processar(db, competencias=competencias_padrao(date.today()), enviar=True)
    finally:
        db.close()

    logger.info(
        "job vencendo: %s clientes, %s aparelhos, %s criados, %s ja existentes, "
        "%s falhas, %s excluidos por OS",
        r["clientes"], r["aparelhos"], r["criados"], r["existentes"],
        r["falhas"], len(r["excluidos"]),
    )
    for p in r["pendencias"]:
        logger.error(
            "job vencendo FALHA aparelho=%s cliente=%s serie=%s vence=%s: %s",
            p["equipamento_cliente_id"], p["cliente_id"], p["serie"],
            p["prox_calibragem"], p["motivo"],
        )


async def loop_mensal(ciclos: Optional[int] = None, dormir=None) -> None:
    """Dorme ate o dia 1, roda, repete.

    `ciclos` limita as voltas e `dormir` troca o sleep — ambos so para teste. Sao
    parametros, e nao monkeypatch de `asyncio.sleep`, de proposito: `tarefas.asyncio`
    E' o modulo global, entao trocar `sleep` ali afeta o event loop inteiro, inclusive
    o do proprio teste (custou um RecursionError e um teste travado ate descobrir).
    """
    dormir = dormir or asyncio.sleep
    volta = 0
    while ciclos is None or volta < ciclos:
        espera = segundos_ate_proxima_mensal(datetime.now(TZ_SP),
                                             settings.JOB_VENCENDO_HORA)
        logger.info("job vencendo: proximo disparo em %.1f dias", espera / 86400)
        await dormir(espera)
        try:
            # Em thread separada: `processar` e' sincrono (SQLAlchemy + httpx) e
            # bloquearia o event loop da API por toda a duracao da carga.
            await asyncio.to_thread(_rodar_job)
        except Exception:
            # Nunca propagar: uma falha aqui mataria a task e o agendamento sumiria
            # em silencio ate o proximo restart. Loga e tenta de novo no mes que vem.
            logger.exception("job vencendo falhou; seguindo para o proximo mes")
        volta += 1


def iniciar(ciclos: Optional[int] = None, dormir=None) -> Optional[asyncio.Task]:
    """Cria a task de fundo, ou None se o job estiver desligado."""
    if not settings.JOB_VENCENDO_ATIVO:
        logger.info("job vencendo: DESLIGADO (JOB_VENCENDO_ATIVO=false)")
        return None
    logger.info("job vencendo: LIGADO, disparo todo dia 1 as %sh (SP)",
                settings.JOB_VENCENDO_HORA)
    return asyncio.create_task(loop_mensal(ciclos, dormir))
