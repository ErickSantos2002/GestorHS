from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, distinct
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, EquipamentoCliente, Solicitacao, Ordem, Fase
from app.api.deps import get_current_usuario
from app.schemas.dashboard import DashboardOut, OsPorFaseItem

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
_FASES_ATIVAS = (4, 5, 6, 7)


@router.get("", response_model=DashboardOut)
def resumo(
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    hoje = date.today()
    limite = hoje + timedelta(days=90)

    ativos = db.query(EquipamentoCliente).filter(
        EquipamentoCliente.ativo.is_(True),
        EquipamentoCliente.prox_calibragem.isnot(None),
    )
    aparelhos_vencidos = ativos.filter(EquipamentoCliente.prox_calibragem < hoje).count()
    aparelhos_vencendo = ativos.filter(
        EquipamentoCliente.prox_calibragem >= hoje,
        EquipamentoCliente.prox_calibragem <= limite,
    ).count()

    solicitacoes_pendentes = (
        db.query(Solicitacao).filter(Solicitacao.status == "pendente").count()
    )

    clientes_a_cobrar = (
        db.query(func.count(distinct(EquipamentoCliente.cliente)))
        .filter(
            EquipamentoCliente.ativo.is_(True),
            EquipamentoCliente.prox_calibragem.isnot(None),
            EquipamentoCliente.prox_calibragem <= limite,
        )
        .scalar()
    ) or 0

    contagem = dict(
        db.query(Ordem.fase, func.count(Ordem.id))
        .filter(Ordem.fase.in_(_FASES_ATIVAS))
        .group_by(Ordem.fase)
        .all()
    )
    fases = (
        db.query(Fase)
        .filter(Fase.id.in_(_FASES_ATIVAS))
        .order_by(Fase.id)
        .all()
    )
    os_por_fase = [
        OsPorFaseItem(fase=f.id, descricao=f.descricao, cor=f.cor, total=int(contagem.get(f.id, 0)))
        for f in fases
    ]

    return DashboardOut(
        aparelhos_vencidos=aparelhos_vencidos,
        aparelhos_vencendo=aparelhos_vencendo,
        solicitacoes_pendentes=solicitacoes_pendentes,
        clientes_a_cobrar=int(clientes_a_cobrar),
        os_por_fase=os_por_fase,
    )
