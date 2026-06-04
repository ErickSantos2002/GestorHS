from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import UsuarioCliente, Cliente, EquipamentoCliente, Ordem
from app.api.deps import get_current_cliente
from app.schemas.portal import PortalMeOut, PortalResumoOut

router = APIRouter(prefix="/portal", tags=["portal"])
_FASES_ATIVAS = (4, 5, 6, 7)


@router.get("/me", response_model=PortalMeOut)
def me(cli: UsuarioCliente = Depends(get_current_cliente), db: Session = Depends(get_db)):
    empresa = db.query(Cliente).filter(Cliente.id == cli.cliente).first()
    return PortalMeOut(
        id=cli.id, login=cli.login, nome=cli.nome, cliente=cli.cliente,
        cliente_nome=empresa.nome if empresa else None,
    )


@router.get("/resumo", response_model=PortalResumoOut)
def resumo(cli: UsuarioCliente = Depends(get_current_cliente), db: Session = Depends(get_db)):
    hoje = date.today()
    base = db.query(EquipamentoCliente).filter(
        EquipamentoCliente.cliente == cli.cliente,
        EquipamentoCliente.ativo.is_(True),
    )
    aparelhos = base.count()
    vencidos = base.filter(EquipamentoCliente.prox_calibragem < hoje).count()
    os_andamento = (
        db.query(Ordem)
        .filter(Ordem.cliente == cli.cliente, Ordem.fase.in_(_FASES_ATIVAS))
        .count()
    )
    return PortalResumoOut(aparelhos=aparelhos, vencidos=vencidos, os_andamento=os_andamento)
