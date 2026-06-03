from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Fase, Funcao
from app.api.deps import get_current_usuario, require_funcao
from app.schemas.fases import FaseOut, FaseUpdate

router = APIRouter(prefix="/fases", tags=["fases"])
ADMIN = "Administrador"


@router.get("", response_model=list[FaseOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    return db.query(Fase).order_by(Fase.id).all()


@router.patch("/{fase_id}", response_model=FaseOut)
def atualizar(fase_id: int, dados: FaseUpdate, db: Session = Depends(get_db),
              _: Usuario = Depends(require_funcao(ADMIN))):
    fase = db.query(Fase).filter(Fase.id == fase_id).first()
    if fase is None:
        raise HTTPException(status_code=404, detail="fase não encontrada")
    if dados.funcao_responsavel is not None:
        if db.query(Funcao).filter(Funcao.id == dados.funcao_responsavel).first() is None:
            raise HTTPException(status_code=404, detail="função não encontrada")
    fase.funcao_responsavel = dados.funcao_responsavel
    db.commit()
    db.refresh(fase)
    return fase
