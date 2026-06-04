from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Solicitacao
from app.api.deps import get_current_usuario, require_funcao
from app.api.ordens_acoes import agora
from app.schemas.solicitacoes import SolicitacaoItem, SolicitacaoPage

router = APIRouter(prefix="/solicitacoes", tags=["solicitacoes"])


@router.get("", response_model=SolicitacaoPage)
def listar(
    status: str | None = None,
    offset: int = 0,
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    query = db.query(Solicitacao)
    if status:
        query = query.filter(Solicitacao.status == status)
    total = query.count()
    pendentes_primeiro = case((Solicitacao.status == "pendente", 0), else_=1)
    items = (
        query.order_by(pendentes_primeiro, Solicitacao.data_solicitacao.desc())
        .offset(offset).limit(limit).all()
    )
    return SolicitacaoPage(items=[SolicitacaoItem.model_validate(s) for s in items], total=total)


@router.post("/{solic_id}/atender", response_model=SolicitacaoItem)
def atender(
    solic_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_funcao("Comercial Pós-Vendas", "Administrador")),
):
    s = db.query(Solicitacao).filter(Solicitacao.id == solic_id).first()
    if s is None:
        raise HTTPException(status_code=404, detail="solicitação não encontrada")
    if s.status != "pendente":
        raise HTTPException(status_code=409, detail="solicitação já atendida")
    s.status = "atendida"
    s.atendido_por = usuario.id
    s.data_atendimento = agora()
    db.commit()
    db.refresh(s)
    return s
