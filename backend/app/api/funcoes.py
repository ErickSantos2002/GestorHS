from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Funcao
from app.api.deps import require_funcao
from app.schemas.acesso import FuncaoOut

router = APIRouter(prefix="/funcoes", tags=["funcoes"])


@router.get("", response_model=list[FuncaoOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(require_funcao("Administrador"))):
    return db.query(Funcao).order_by(Funcao.id).all()
