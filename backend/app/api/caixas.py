from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status as http_status, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Caixa, Ordem, Fase
from app.core import os_workflow as wf
from app.core.caixa import contar_outros, principal_valido
from app.api.deps import get_current_usuario, require_funcao
from app.api.cadastros_common import excluir_protegido
from app.schemas.caixas import (
    CaixaCreate, CaixaUpdate, CaixaOut, CaixaDetalhe, CaixaPage, VincularOrdemIn,
    CaixaQuadroItem, QuadroCaixaColuna,
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


@router.get("/quadro", response_model=list[QuadroCaixaColuna])
def quadro_caixas(cliente: int | None = None, db: Session = Depends(get_db),
                  _: Usuario = Depends(get_current_usuario)):
    fases_ids = list(wf.ATIVAS)
    fases = {f.id: f for f in db.query(Fase).filter(Fase.id.in_(fases_ids)).all()}
    colunas = []
    for fid in fases_ids:
        q = db.query(Caixa).filter(Caixa.fase == fid)
        caixas = q.order_by(Caixa.id.desc()).all()
        itens = []
        for cx in caixas:
            ativas = [o for o in cx.ordens if wf.eh_ativa(o.fase)]
            if cliente is not None and not any(o.cliente == cliente for o in ativas):
                continue
            prontos = sum(1 for o in ativas if o.desfecho_lab in wf.DESFECHOS_TERMINAIS)
            clientes_ids = [o.cliente for o in ativas]
            pid = principal_valido(cx.cliente_principal, clientes_ids)
            if pid is not None:
                principal_nome = cx.cliente_principal_nome
            else:
                principal_nome = next((o.cliente_nome for o in ativas), None)
            outros = contar_outros(clientes_ids)
            itens.append(CaixaQuadroItem(
                id=cx.id, cliente_nome=principal_nome, cliente_principal_nome=principal_nome,
                total_os=len(ativas), prontos=prontos, pendentes=len(ativas) - prontos,
                outros_clientes=outros))
        f = fases.get(fid)
        colunas.append(QuadroCaixaColuna(
            fase=fid, descricao=f.descricao if f else str(fid),
            cor=f.cor if f else "888", total=len(itens), caixas=itens))
    return colunas


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
    ordem.caixa = cx.id  # vincula/move (multi-cliente permitido; principal define as integracoes)
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

    if origem == wf.FASE_RECEBIDO:
        clientes_distintos = {o.cliente for o in ativas}
        if dados.cliente_principal is not None:
            if dados.cliente_principal not in clientes_distintos:
                raise HTTPException(status_code=409, detail="cliente principal deve ser um cliente da caixa")
            cx.cliente_principal = dados.cliente_principal
        if cx.cliente_principal is None:
            if len(clientes_distintos) == 1:
                cx.cliente_principal = next(iter(clientes_distintos))
            elif len(clientes_distintos) > 1:
                raise HTTPException(status_code=409, detail="defina o cliente principal antes de avancar")

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
        texto = f"Caixa #{cx.id}: {origem} -> {destino}"
        if dados.obs and dados.obs.strip():
            texto = f"{texto} - {dados.obs.strip()}"
        registrar_log(db, o, usuario, texto)
    cx.fase = destino
    db.commit()
    db.refresh(cx)
    agendar_espelhamento_caixa(db, background_tasks, cx)
    if origem == wf.FASE_LABORATORIO:
        agendar_card_caixa(db, background_tasks, cx)
    return cx


@router.post("/{caixa_id}/cancelar", response_model=CaixaDetalhe)
def cancelar_caixa(
    caixa_id: int,
    dados: CaixaCancelarIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_usuario),
):
    cx = _get_caixa(db, caixa_id)
    if cx.fase is None:
        raise HTTPException(status_code=409, detail="caixa sem fase ativa")
    exige_funcao_da_fase(db, usuario, cx.fase)
    origem = cx.fase
    for o in _ordens_ativas(cx):
        o.fase = wf.FASE_CANCELADA
        o.situacao = "C"
        registrar_log(db, o, usuario, f"Caixa #{cx.id} cancelada: {dados.motivo}")
    cx.fase = None
    db.commit()
    db.refresh(cx)
    agendar_espelhamento_caixa(db, background_tasks, cx, origem=origem, arquivado=True)
    return cx
