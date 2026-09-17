"""Worker de reenvio: varre as Empresas paradas em `pendente` e tenta o Tiny de novo.

Por que existe: o espelhamento no Tiny e' best-effort e disparado por gatilho
(criar, editar, botao Reenviar). Quando a tentativa falha por algo transitorio —
rede, limite de chamadas, pesquisa inconclusiva — a Empresa fica `pendente` e,
ate 17/09/2026, NADA tentava de novo: so alguem clicando em Reenviar. Na pratica
`pendente` era um beco sem saida, e foi assim que uma falha de FOR UPDATE passou
um dia inteiro sem ninguem notar (ver integrations/tiny_client.stmt_travar_empresa).

Por que aqui e nao em cron: mesmo motivo do worker de vencendo — producao sobe no
Easypanel a partir do Dockerfile, onde agendar significa instalar cron na imagem
ou depender de servico externo. O backend e' um servico unico e `sincronizar_empresa`
e' idempotente (adota o contato que ja existe em vez de criar outro, com a linha
travada durante a operacao), entao um agendador embutido sobe junto com o deploy.

So mexe em `tiny_status == 'pendente'`. `erro` e' recusa do Tiny que nao muda
sozinha (documento invalido, por exemplo): repetir a cada 10 minutos gastaria
chamada para sempre contra uma conta limitada a 20 por minuto. Cadastro com status
nulo e' anterior a integracao e continua sendo trabalho do script de carga
(`app.scripts.enviar_empresas_tiny`), que e' conferido a mao de proposito.

Nasce DESLIGADO (`JOB_TINY_ATIVO=false`): a maquina de desenvolvimento aponta para
o banco de producao com o token real, e o Tiny nao tem ambiente de teste.
"""
import asyncio
import logging
import time
from typing import Optional

from app.core.config import settings
from app.integrations import tiny_client
from app.models import Empresa
from app.models.database import SessionLocal

logger = logging.getLogger(__name__)

# Cada empresa gasta DUAS chamadas (pesquisa + inclusao/alteracao) e a conta
# permite 20 por minuto, dai ~7s entre elas — mesma conta do script de carga.
PAUSA_PADRAO = 7.0


def pendentes(db, limite: int) -> list:
    """Empresas ativas paradas em `pendente`, a mais antiga primeiro.

    A ordem por `tiny_em` importa quando a fila passa do teto da volta: sem ela,
    a mesma empresa do topo do id seria tentada toda vez e o resto nunca sairia.
    """
    return (db.query(Empresa)
            .filter(Empresa.ativo.is_(True), Empresa.tiny_status == "pendente")
            .order_by(Empresa.tiny_em.asc().nullsfirst(), Empresa.id)
            .limit(limite)
            .all())


def _rodar_job(pausa: float = PAUSA_PADRAO) -> dict:
    """Uma varredura. Reusa `sincronizar_empresa`, que e' o mesmo caminho do botao
    Reenviar — e o unico que trata tanto a empresa sem `tiny_id` quanto a que ja
    tem (o script de carga filtra `tiny_id IS NULL` e pularia a segunda)."""
    db = SessionLocal()
    try:
        fila = pendentes(db, settings.JOB_TINY_LIMITE)
        if not fila:
            return {"tentadas": 0}
        logger.info("job tiny: %s empresa(s) pendente(s) para reenviar", len(fila))
        for i, empresa in enumerate(fila):
            if i and pausa:
                time.sleep(pausa)
            # Nunca levanta: marca o proprio estado da empresa e loga.
            tiny_client.sincronizar_empresa(empresa.id)
        return {"tentadas": len(fila)}
    finally:
        db.close()


async def loop(ciclos: Optional[int] = None, dormir=None) -> None:
    """Dorme o intervalo, varre, repete.

    `ciclos` e `dormir` sao parametros (e nao monkeypatch de `asyncio.sleep`) pelo
    mesmo motivo documentado no worker de vencendo: `tarefas.asyncio` e' o modulo
    global, entao trocar `sleep` ali afeta o event loop inteiro, inclusive o do teste.
    """
    dormir = dormir or asyncio.sleep
    volta = 0
    while ciclos is None or volta < ciclos:
        await dormir(settings.JOB_TINY_INTERVALO_MIN * 60)
        try:
            # Em thread separada: `sincronizar_empresa` e' sincrono (SQLAlchemy +
            # httpx) e bloquearia o event loop da API por toda a varredura.
            await asyncio.to_thread(_rodar_job)
        except Exception:
            # Nunca propagar: uma falha aqui mataria a task e o agendamento sumiria
            # em silencio ate o proximo restart.
            logger.exception("job tiny falhou; seguindo para a proxima volta")
        volta += 1


def iniciar(ciclos: Optional[int] = None, dormir=None) -> Optional[asyncio.Task]:
    """Cria a task de fundo, ou None se o job estiver desligado ou sem token."""
    if not settings.JOB_TINY_ATIVO:
        logger.info("job tiny: DESLIGADO (JOB_TINY_ATIVO=false)")
        return None
    if not tiny_client.integracao_ativa():
        logger.info("job tiny: DESLIGADO (sem TINY_TOKEN)")
        return None
    logger.info("job tiny: LIGADO, varredura a cada %s min (ate %s por volta)",
                settings.JOB_TINY_INTERVALO_MIN, settings.JOB_TINY_LIMITE)
    return asyncio.create_task(loop(ciclos, dormir))
