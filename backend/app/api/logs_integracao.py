from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, LogIntegracao
from app.api.deps import require_funcao
from app.integrations import taskhs_client, hsgrowth_client
from app.schemas.logs_integracao import LogsPage, LogIntegracaoOut, EstadoIntegracoes

router = APIRouter(prefix="/logs-integracao", tags=["integracao"])
ADMIN = "Administrador"


@router.get("", response_model=LogsPage)
def listar(
    integracao: str | None = None,
    status: str | None = None,
    tipo: str | None = None,
    os: int | None = None,
    q: str | None = None,
    offset: int = 0,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_funcao(ADMIN)),
):
    query = db.query(LogIntegracao)
    if integracao:
        query = query.filter(LogIntegracao.integracao == integracao)
    if status:
        query = query.filter(LogIntegracao.status == status)
    if tipo:
        query = query.filter(LogIntegracao.tipo == tipo)
    if os is not None:
        query = query.filter(LogIntegracao.referencia_os == os)
    if q:
        termo = f"%{q}%"
        query = query.filter(or_(LogIntegracao.external_id.ilike(termo),
                                 LogIntegracao.resposta.ilike(termo)))
    total = query.count()
    items = query.order_by(LogIntegracao.id.desc()).offset(offset).limit(limit).all()
    estado = EstadoIntegracoes(
        taskhs_ativo=taskhs_client.integracao_ativa(),
        growthhs_ativo=hsgrowth_client.integracao_ativa(),
    )
    return LogsPage(items=[LogIntegracaoOut.model_validate(i) for i in items],
                    total=total, estado=estado)
