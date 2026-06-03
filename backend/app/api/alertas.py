from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, case, or_
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, EquipamentoCliente, Cliente
from app.api.deps import get_current_usuario
from app.schemas.alertas import AlertaItem, AlertaPage

router = APIRouter(prefix="/alertas", tags=["alertas"])


@router.get("", response_model=AlertaPage)
def listar(
    q: str | None = None,
    ocultar_recentes: bool = False,
    offset: int = 0,
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    hoje = date.today()
    limite = hoje + timedelta(days=90)
    vencidos = func.sum(case((EquipamentoCliente.prox_calibragem < hoje, 1), else_=0)).label("vencidos")
    vencendo = func.sum(case((EquipamentoCliente.prox_calibragem >= hoje, 1), else_=0)).label("vencendo")
    prox_antiga = func.min(EquipamentoCliente.prox_calibragem).label("prox_antiga")
    ult_contato = func.max(EquipamentoCliente.ult_aviso).label("ult_contato")

    base = (
        db.query(
            EquipamentoCliente.cliente.label("cliente"),
            Cliente.nome.label("cliente_nome"),
            vencidos, vencendo, prox_antiga, ult_contato,
        )
        .join(Cliente, EquipamentoCliente.cliente == Cliente.id)
        .filter(
            EquipamentoCliente.ativo.is_(True),
            EquipamentoCliente.prox_calibragem.isnot(None),
            EquipamentoCliente.prox_calibragem <= limite,
        )
        .group_by(EquipamentoCliente.cliente, Cliente.nome)
    )
    if q:
        base = base.filter(Cliente.nome.ilike(f"%{q}%"))
    if ocultar_recentes:
        corte = datetime.now(timezone.utc) - timedelta(days=30)
        base = base.having(or_(
            func.max(EquipamentoCliente.ult_aviso).is_(None),
            func.max(EquipamentoCliente.ult_aviso) < corte,
        ))
    base = base.order_by(vencidos.desc(), prox_antiga.asc())

    linhas = base.all()
    total = len(linhas)
    pagina = linhas[offset: offset + limit]
    items = [
        AlertaItem(
            cliente=r.cliente, cliente_nome=r.cliente_nome,
            vencidos=int(r.vencidos or 0), vencendo=int(r.vencendo or 0),
            prox_antiga=r.prox_antiga, ult_contato=r.ult_contato,
        )
        for r in pagina
    ]
    return AlertaPage(items=items, total=total)
