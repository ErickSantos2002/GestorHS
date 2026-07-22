from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status as http_status, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Caixa, Ordem
from app.core import os_workflow as wf
from app.api.deps import get_current_usuario, require_funcao
from app.api.cadastros_common import excluir_protegido
from app.schemas.caixas import (
    CaixaCreate, CaixaUpdate, CaixaOut, CaixaDetalhe, CaixaPage, VincularOrdemIn,
)
from app.schemas.caixa_acoes import CaixaAvancarIn, CaixaCancelarIn
from app.api.ordens_acoes import registrar_log, exige_funcao_da_fase, agora, espelhar_calibracao
from app.api.espelhamento import agendar_espelhamento_caixa
from app.api.growthhs_cards import agendar_card_caixa

router = APIRouter(prefix="/caixas", tags=["caixas"])

_escrita = require_funcao("Expedição", "Administrador")


def _get_caixa(db: Session, caixa_id: int) -> Caixa:
    cx = db.query(Caixa).filter(Caixa.id == caixa_id).first()
    if cx is None:
        raise HTTPException(status_code=404, detail="caixa não encontrada")
    return cx


def _cliente_da_caixa(cx: Caixa) -> int | None:
    """O cliente das OS ativas da caixa (todas iguais por invariante), ou None se vazia."""
    for o in cx.ordens:
        return o.cliente
    return None


def _exige_mesmo_cliente(cx: Caixa, cliente_id: int) -> None:
    atual = _cliente_da_caixa(cx)
    if atual is not None and atual != cliente_id:
        raise HTTPException(status_code=409, detail="OS de cliente diferente do da caixa")


@router.get("", response_model=CaixaPage)
def listar(
    q: str | None = None,
    incluir_concluidas: bool = False,
    offset: int = 0,
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    query = db.query(Caixa)
    if q:
        if q.strip().isdigit():
            query = query.filter(Caixa.id == int(q.strip()))
        else:
            query = query.filter(Caixa.obs.ilike(f"%{q.strip()}%"))
    if not incluir_concluidas:
        # Oculta caixas "concluidas": tem OS e nenhuma ativa (todas terminais).
        # Mantem visiveis as vazias e as que tem ao menos uma OS ativa.
        tem_ativa = db.query(Ordem.id).filter(
            Ordem.caixa == Caixa.id, Ordem.fase.in_(wf.ATIVAS)
        ).exists()
        sem_ordens = ~db.query(Ordem.id).filter(Ordem.caixa == Caixa.id).exists()
        query = query.filter(or_(tem_ativa, sem_ordens))
    total = query.count()
    items = query.order_by(Caixa.id.desc()).offset(offset).limit(limit).all()
    return CaixaPage(items=[CaixaOut.model_validate(c) for c in items], total=total)


@router.get("/{caixa_id}", response_model=CaixaDetalhe)
def obter(caixa_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    return _get_caixa(db, caixa_id)


@router.post("", response_model=CaixaOut, status_code=http_status.HTTP_201_CREATED)
def criar(dados: CaixaCreate, db: Session = Depends(get_db), _: Usuario = Depends(_escrita)):
    cx = Caixa(data=date.today(), obs=dados.obs)
    db.add(cx)
    db.commit()
    db.refresh(cx)
    return cx


@router.patch("/{caixa_id}", response_model=CaixaOut)
def atualizar(caixa_id: int, dados: CaixaUpdate, db: Session = Depends(get_db), _: Usuario = Depends(_escrita)):
    cx = _get_caixa(db, caixa_id)
    for chave, valor in dados.model_dump(exclude_unset=True).items():
        setattr(cx, chave, valor)
    db.commit()
    db.refresh(cx)
    return cx


@router.delete("/{caixa_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def excluir(caixa_id: int, db: Session = Depends(get_db), _: Usuario = Depends(_escrita)):
    cx = _get_caixa(db, caixa_id)
    if cx.ordens:
        raise HTTPException(status_code=409, detail="caixa possui OS vinculadas")
    excluir_protegido(db, cx)


@router.post("/{caixa_id}/ordens", response_model=CaixaDetalhe)
def vincular_ordem(
    caixa_id: int,
    dados: VincularOrdemIn,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_escrita),
):
    cx = _get_caixa(db, caixa_id)
    ordem = db.query(Ordem).filter(Ordem.id == dados.ordem_id).first()
    if ordem is None:
        raise HTTPException(status_code=404, detail="OS não encontrada")
    _exige_mesmo_cliente(cx, ordem.cliente)
    ordem.caixa = cx.id  # vincula/move (mesmo cliente garantido acima)
    registrar_log(db, ordem, usuario, f"OS vinculada à caixa #{cx.id}")
    db.commit()
    db.refresh(cx)
    return cx


@router.delete("/{caixa_id}/ordens/{ordem_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def desvincular_ordem(
    caixa_id: int,
    ordem_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_escrita),
):
    cx = _get_caixa(db, caixa_id)
    ordem = db.query(Ordem).filter(Ordem.id == ordem_id, Ordem.caixa == cx.id).first()
    if ordem is None:
        raise HTTPException(status_code=404, detail="OS não está nesta caixa")
    ordem.caixa = None
    registrar_log(db, ordem, usuario, f"OS removida da caixa #{cx.id}")
    db.commit()


def _ordens_ativas(cx: Caixa) -> list[Ordem]:
    return [o for o in cx.ordens if wf.eh_ativa(o.fase)]


@router.post("/{caixa_id}/avancar", response_model=CaixaDetalhe)
def avancar_caixa(
    caixa_id: int,
    dados: CaixaAvancarIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_usuario),
):
    cx = _get_caixa(db, caixa_id)
    if cx.fase is None:
        raise HTTPException(status_code=409, detail="caixa sem fase ativa")
    exige_funcao_da_fase(db, usuario, cx.fase)
    origem = cx.fase
    destino = wf.proxima_fase(origem)
    ativas = _ordens_ativas(cx)

    ok, motivo = wf.pode_avancar_caixa(origem, [o.desfecho_lab for o in ativas])
    if not ok:
        raise HTTPException(status_code=409, detail=motivo)

    # efeito por fase, fan-out para cada OS ativa
    if origem == 7:  # Preparando -> Finalizada
        if not (dados.cod_retorno and dados.cod_retorno.strip()):
            raise HTTPException(status_code=422, detail="cod_retorno é obrigatório para finalizar")
    for o in ativas:
        if origem == wf.FASE_LABORATORIO:
            if o.desfecho_lab == wf.DESFECHO_CONCLUIDO:
                espelhar_calibracao(db, o)
        elif origem == 6:      # Pós-Vendas -> Financeiro
            o.aceite = True
            o.data_aceite = agora()
        elif origem == 10:     # Financeiro -> Preparando
            if not o.nota_fiscal:
                raise HTTPException(status_code=409, detail="anexe a nota fiscal da caixa antes de confirmar o pagamento")
            o.pago = True
            o.data_pagamento = agora()
        elif origem == 7:      # Preparando -> Finalizada
            o.cod_retorno = dados.cod_retorno.strip()
            o.data_retorno = agora()
            o.situacao = "F"
        o.fase = destino
        registrar_log(db, o, usuario, f"Caixa #{cx.id}: {origem} -> {destino}")
    cx.fase = destino
    db.commit()
    db.refresh(cx)
    agendar_espelhamento_caixa(db, background_tasks, cx)
    if origem == wf.FASE_LABORATORIO:
        agendar_card_caixa(db, background_tasks, cx)
    return cx
