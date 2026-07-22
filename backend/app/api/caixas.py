from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status as http_status, Query
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
from app.api.ordens_acoes import registrar_log

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
