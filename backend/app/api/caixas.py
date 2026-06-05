from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status as http_status, Query
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Caixa
from app.api.deps import get_current_usuario, require_funcao
from app.api.cadastros_common import excluir_protegido
from app.core import caixas_workflow as cw
from app.schemas.caixas import (
    CaixaCreate, CaixaUpdate, CaixaOut, CaixaDetalhe, CaixaPage,
)

router = APIRouter(prefix="/caixas", tags=["caixas"])

_escrita = require_funcao("Expedição", "Administrador")


def _get_caixa(db: Session, caixa_id: int) -> Caixa:
    cx = db.query(Caixa).filter(Caixa.id == caixa_id).first()
    if cx is None:
        raise HTTPException(status_code=404, detail="caixa não encontrada")
    return cx


@router.get("", response_model=CaixaPage)
def listar(
    status: str | None = None,
    q: str | None = None,
    offset: int = 0,
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    query = db.query(Caixa)
    if status:
        query = query.filter(Caixa.status == status)
    if q:
        if q.strip().isdigit():
            query = query.filter(Caixa.id == int(q.strip()))
        else:
            query = query.filter(Caixa.obs.ilike(f"%{q.strip()}%"))
    total = query.count()
    items = query.order_by(Caixa.id.desc()).offset(offset).limit(limit).all()
    return CaixaPage(items=[CaixaOut.model_validate(c) for c in items], total=total)


@router.get("/{caixa_id}", response_model=CaixaDetalhe)
def obter(caixa_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    return _get_caixa(db, caixa_id)


@router.post("", response_model=CaixaOut, status_code=http_status.HTTP_201_CREATED)
def criar(dados: CaixaCreate, db: Session = Depends(get_db), _: Usuario = Depends(_escrita)):
    cx = Caixa(data=date.today(), status=cw.PENDENTE, obs=dados.obs)
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


def _transicionar(db: Session, cx: Caixa, novo: str) -> Caixa:
    try:
        cw.validar_transicao(cx.status, novo)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    cx.status = novo
    db.commit()
    db.refresh(cx)
    return cx


@router.post("/{caixa_id}/abrir", response_model=CaixaOut)
def abrir_caixa(caixa_id: int, db: Session = Depends(get_db), _: Usuario = Depends(_escrita)):
    return _transicionar(db, _get_caixa(db, caixa_id), cw.ABERTA)


@router.post("/{caixa_id}/finalizar", response_model=CaixaOut)
def finalizar_caixa(caixa_id: int, db: Session = Depends(get_db), _: Usuario = Depends(_escrita)):
    return _transicionar(db, _get_caixa(db, caixa_id), cw.FINALIZADA)


@router.delete("/{caixa_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def excluir(caixa_id: int, db: Session = Depends(get_db), _: Usuario = Depends(_escrita)):
    cx = _get_caixa(db, caixa_id)
    if cx.ordens:
        raise HTTPException(status_code=409, detail="caixa possui OS vinculadas")
    excluir_protegido(db, cx)
