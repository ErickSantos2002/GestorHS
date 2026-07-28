"""Endpoint inbound chamado pelo GrowthHS: ao marcar uma proposta como "Ganho",
o card correspondente precisa mover a caixa de Pos-Vendas(6) para Financeiro(10)
no GestorHS. Autenticado por API key fixa (`require_growthhs_inbound`, T1), nao
por JWT — quem chama e o GrowthHS, nao um usuario logado."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Caixa
from app.api.deps import require_growthhs_inbound
from app.api.caixas import executar_avanco_caixa, _ordens_ativas
from app.core import os_workflow as wf

router = APIRouter(prefix="/integracao/growthhs", tags=["integracao-growthhs"])

FASE_POSVENDAS = 6
# Fases que ja passaram do ponto de avanco (10/7/8): chamada repetida vira no-op,
# nao erro — o GrowthHS nao sabe se ja mandou essa mesma "ganho" antes.
_FASES_JA_AVANCADAS = (wf.FASE_FINANCEIRO, 7, wf.FASE_FINALIZADA)


class GanhoIn(BaseModel):
    observacao: str | None = None


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
        raise HTTPException(status_code=404, detail="caixa nao encontrada")
    if cx.fase in _FASES_JA_AVANCADAS:
        return GanhoOut(movida=False, caixa_id=cx.id, fase=cx.fase)
    if cx.fase != FASE_POSVENDAS:
        raise HTTPException(status_code=409, detail="caixa nao esta em Pos-Vendas")

    obs = "via GrowthHS"
    if dados.observacao and dados.observacao.strip():
        obs = f"via GrowthHS: {dados.observacao.strip()}"

    executar_avanco_caixa(
        db, cx,
        origem=FASE_POSVENDAS,
        destino=wf.proxima_fase(FASE_POSVENDAS),
        ativas=_ordens_ativas(cx),
        usuario=None,
        obs=obs,
        cod_retorno=None,
        background_tasks=background_tasks,
    )
    return GanhoOut(movida=True, caixa_id=cx.id, fase=cx.fase)
