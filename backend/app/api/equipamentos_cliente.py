from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, status as http_status, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, EquipamentoCliente, HistoricoEquipamento
from app.api.deps import get_current_usuario, require_funcao
from app.api.cadastros_common import excluir_protegido
from app.schemas.frota import (
    FrotaListOut, FrotaPage, EquipamentoClienteOut,
    EquipamentoClienteCreate, EquipamentoClienteUpdate, HistoricoOut,
)

router = APIRouter(prefix="/equipamentos-cliente", tags=["frota"])
ADMIN = "Administrador"


@router.get("", response_model=FrotaPage)
def listar(
    cliente: int | None = None,
    status: str | None = None,
    q: str | None = None,
    offset: int = 0,
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    query = db.query(EquipamentoCliente)
    if cliente is not None:
        query = query.filter(EquipamentoCliente.cliente == cliente)
    if status:
        hoje = date.today()
        if status == "vencido":
            query = query.filter(EquipamentoCliente.prox_calibragem < hoje)
        elif status == "vencendo":
            query = query.filter(
                EquipamentoCliente.prox_calibragem >= hoje,
                EquipamentoCliente.prox_calibragem <= hoje + timedelta(days=90),
            )
        elif status == "em_dia":
            query = query.filter(EquipamentoCliente.prox_calibragem > hoje + timedelta(days=90))
        elif status == "sem_data":
            query = query.filter(EquipamentoCliente.prox_calibragem.is_(None))
    if q:
        termo = f"%{q}%"
        query = query.filter(or_(EquipamentoCliente.serie.ilike(termo), EquipamentoCliente.patrimonio.ilike(termo)))
    total = query.count()
    items = query.order_by(EquipamentoCliente.id).offset(offset).limit(limit).all()
    return FrotaPage(items=[FrotaListOut.model_validate(e) for e in items], total=total)


@router.get("/{item_id}", response_model=EquipamentoClienteOut)
def obter(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    obj = db.query(EquipamentoCliente).filter(EquipamentoCliente.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    return obj


@router.get("/{item_id}/historico", response_model=list[HistoricoOut])
def historico(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    if db.query(EquipamentoCliente).filter(EquipamentoCliente.id == item_id).first() is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    return (
        db.query(HistoricoEquipamento)
        .filter(HistoricoEquipamento.equipamento_cliente == item_id)
        .order_by(HistoricoEquipamento.id)
        .all()
    )


@router.post("", response_model=EquipamentoClienteOut, status_code=http_status.HTTP_201_CREATED)
def criar(dados: EquipamentoClienteCreate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = EquipamentoCliente(**dados.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{item_id}", response_model=EquipamentoClienteOut)
def atualizar(item_id: int, dados: EquipamentoClienteUpdate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(EquipamentoCliente).filter(EquipamentoCliente.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    for chave, valor in dados.model_dump(exclude_unset=True).items():
        setattr(obj, chave, valor)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{item_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def excluir(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(EquipamentoCliente).filter(EquipamentoCliente.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    excluir_protegido(db, obj)
