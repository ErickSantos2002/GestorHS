from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, TipoCalibragem
from app.api.deps import get_current_usuario
from app.schemas.ordens import TipoCalibragemOut

router = APIRouter(prefix="/tipos-calibragem", tags=["tipos-calibragem"])


@router.get("", response_model=list[TipoCalibragemOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    return db.query(TipoCalibragem).order_by(TipoCalibragem.descricao).all()
