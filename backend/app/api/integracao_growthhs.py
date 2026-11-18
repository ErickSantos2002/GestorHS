"""Endpoint inbound chamado pelo GrowthHS: ao marcar uma proposta como "Ganho",
o card correspondente precisa mover a caixa de Pos-Vendas(6) para Financeiro(10)
no GestorHS. Autenticado por API key fixa (`require_growthhs_inbound`, T1), nao
por JWT — quem chama e o GrowthHS, nao um usuario logado.

Tambem expoe `PUT /caixas/{id}/proposta`: o CRM troca o numero da proposta da caixa
(erro de digitacao no card) com a mesma regra da tela — `aplicar_troca_proposta`.

A regra "essa caixa pode avancar agora?" vive em `core/avanco_inbound.py`, e e'
compartilhada com o inbound do TaskHS (`api/integracao_taskhs.py`)."""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Caixa
from app.api.deps import require_growthhs_inbound
from app.api.caixas import aplicar_troca_proposta, executar_avanco_caixa, _ordens_ativas
from app.core import os_workflow as wf
from app.core import avanco_inbound as ai

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integracao/growthhs", tags=["integracao-growthhs"])


class GanhoIn(BaseModel):
    observacao: str | None = None
    numero_proposta: int | None = None


class GanhoOut(BaseModel):
    movida: bool
    caixa_id: int
    fase: int


@router.post("/caixas/{caixa_id}/ganho", response_model=GanhoOut)
def ganho(
    caixa_id: int,
    dados: GanhoIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: None = Depends(require_growthhs_inbound),
):
    cx = db.query(Caixa).filter(Caixa.id == caixa_id).first()
    if cx is None:
        logger.warning("GrowthHS ganho: caixa %s nao encontrada", caixa_id)
        raise HTTPException(status_code=404, detail="caixa nao encontrada")
    estado = ai.estado_para_avanco(cx.fase)
    if estado == ai.NO_OP:
        logger.info("GrowthHS ganho: caixa %s ja avancada (fase %s), no-op", caixa_id, cx.fase)
        if dados.numero_proposta is not None:
            cx.numero_proposta = dados.numero_proposta
            db.commit()
        return GanhoOut(movida=False, caixa_id=cx.id, fase=cx.fase)
    if estado != ai.AVANCAR:
        logger.warning("GrowthHS ganho: caixa %s nao esta em Pos-Vendas (fase %s)", caixa_id, cx.fase)
        raise HTTPException(status_code=409, detail="caixa nao esta em Pos-Vendas")

    obs = "via GrowthHS"
    if dados.observacao and dados.observacao.strip():
        obs = f"via GrowthHS: {dados.observacao.strip()}"

    if dados.numero_proposta is not None:
        cx.numero_proposta = dados.numero_proposta

    executar_avanco_caixa(
        db, cx,
        origem=wf.FASE_POSVENDAS,
        destino=wf.proxima_fase(wf.FASE_POSVENDAS),
        ativas=_ordens_ativas(cx),
        usuario=None,
        obs=obs,
        cod_retorno=None,
        background_tasks=background_tasks,
    )
    logger.info("GrowthHS ganho: caixa %s movida para Financeiro", caixa_id)
    return GanhoOut(movida=True, caixa_id=cx.id, fase=cx.fase)


class TrocaPropostaIn(BaseModel):
    numero: int
    observacao: str | None = None


class TrocaPropostaOut(BaseModel):
    caixa_id: int
    numero_proposta: int
    alterada: bool


@router.put("/caixas/{caixa_id}/proposta", response_model=TrocaPropostaOut)
def trocar_proposta(
    caixa_id: int,
    dados: TrocaPropostaIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: None = Depends(require_growthhs_inbound),
):
    """O CRM chama ANTES de gravar o numero da proposta no card e so grava se aqui
    aceitar; o `detail` das recusas vira o toast do usuario la. Mesma regra da tela
    (`aplicar_troca_proposta`), valida em qualquer fase ativa — inclusive antes do
    Ganho. Nao mexe em faturamento nem avanca a caixa."""
    cx = db.query(Caixa).filter(Caixa.id == caixa_id).first()
    if cx is None:
        raise HTTPException(status_code=404, detail=f"caixa #{caixa_id} não encontrada no GestorHS")
    origem = "via GrowthHS"
    if dados.observacao and dados.observacao.strip():
        origem = f"via GrowthHS: {dados.observacao.strip()}"
    alterada = aplicar_troca_proposta(db, cx, dados.numero, None, background_tasks, origem=origem)
    logger.info("GrowthHS proposta: caixa %s -> #%s (alterada=%s)", caixa_id, dados.numero, alterada)
    return TrocaPropostaOut(caixa_id=cx.id, numero_proposta=cx.numero_proposta, alterada=alterada)
