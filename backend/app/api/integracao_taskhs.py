"""Endpoint inbound chamado pela automacao do TaskHS: quando o card entra na lista
do Financeiro (205), a caixa correspondente avanca de Pos-Vendas(6) para
Financeiro(10) no GestorHS. Autenticado por API key propria
(`require_taskhs_inbound`), nao por JWT — quem chama e' o TaskHS.

Existe porque a caixa com Phoebus nao tem proposta no GrowthHS, logo nao tem o
gatilho de "Ganho" que move a caixa normal. O setor de Servicos trabalha no board
do TaskHS, e mover o card ja e' o gesto que significa "servico terminou".

A regra "essa caixa pode avancar agora?" vive em `core/avanco_inbound.py`,
compartilhada com o inbound do GrowthHS."""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.caixas import executar_avanco_caixa, _ordens_ativas
from app.api.deps import require_taskhs_inbound
from app.core import avanco_inbound as ai
from app.core import os_workflow as wf
from app.core.config import settings
from app.models import Caixa
from app.models.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integracao/taskhs", tags=["integracao-taskhs"])


class FinanceiroIn(BaseModel):
    card_id: int | None = None
    observacao: str | None = None


class FinanceiroOut(BaseModel):
    movida: bool
    caixa_id: int
    fase: int


def _tem_phoebus(ativas) -> bool:
    """Trava de escopo, POSITIVA de proposito.

    ⚠️ NAO escreva `not fluxo_modulo.caixa_so_de_modulo(ativas)`: isso deixaria
    passar a caixa NORMAL (sem Phoebus e sem modulo), que e' exatamente o caso que
    a decisao do `aceite` quer barrar. Sair da fase 6 grava `aceite`/`data_aceite`,
    e na caixa normal esse aval vem do "Ganho" da proposta no GrowthHS.
    """
    return any(getattr(o, "equipamento_catalogo", None) == settings.EQUIPAMENTO_PHOEBUS_ID
               for o in ativas)


@router.post("/caixas/{caixa_id}/financeiro", response_model=FinanceiroOut)
def financeiro(
    caixa_id: int,
    dados: FinanceiroIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: None = Depends(require_taskhs_inbound),
):
    cx = db.query(Caixa).filter(Caixa.id == caixa_id).first()
    if cx is None:
        logger.warning("TaskHS financeiro: caixa %s nao encontrada (card=%s)",
                       caixa_id, dados.card_id)
        raise HTTPException(status_code=404, detail="caixa nao encontrada")

    estado = ai.estado_para_avanco(cx.fase)
    if estado == ai.NO_OP:
        logger.info("TaskHS financeiro: caixa %s ja avancada (fase %s), no-op",
                    caixa_id, cx.fase)
        return FinanceiroOut(movida=False, caixa_id=cx.id, fase=cx.fase)

    ativas = _ordens_ativas(cx)
    if not _tem_phoebus(ativas):
        logger.warning("TaskHS financeiro: caixa %s nao tem Phoebus (card=%s)",
                       caixa_id, dados.card_id)
        raise HTTPException(
            status_code=409,
            detail="caixa sem Phoebus: avanco pelo TaskHS nao se aplica")

    if estado != ai.AVANCAR:
        logger.warning("TaskHS financeiro: caixa %s nao esta em Pos-Vendas (fase %s)",
                       caixa_id, cx.fase)
        raise HTTPException(status_code=409, detail="caixa nao esta em Pos-Vendas")

    obs = "via TaskHS"
    if dados.observacao and dados.observacao.strip():
        obs = f"via TaskHS: {dados.observacao.strip()}"

    executar_avanco_caixa(
        db, cx,
        origem=wf.FASE_POSVENDAS,
        destino=wf.proxima_fase(wf.FASE_POSVENDAS),
        ativas=ativas,
        usuario=None,
        obs=obs,
        cod_retorno=None,
        background_tasks=background_tasks,
    )
    logger.info("TaskHS financeiro: caixa %s movida para Financeiro (card=%s)",
                caixa_id, dados.card_id)
    return FinanceiroOut(movida=True, caixa_id=cx.id, fase=cx.fase)
