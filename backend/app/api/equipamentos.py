from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Equipamento
from app.api.deps import get_current_usuario, require_funcao
from app.api.cadastros_common import excluir_protegido
from app.schemas.cadastros import EquipamentoOut, EquipamentoCreate, EquipamentoUpdate

router = APIRouter(prefix="/equipamentos", tags=["equipamentos"])
ADMIN = "Administrador"


@router.get("", response_model=list[EquipamentoOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    return db.query(Equipamento).order_by(Equipamento.id).all()


@router.get("/{item_id}", response_model=EquipamentoOut)
def obter(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    obj = db.query(Equipamento).filter(Equipamento.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    return obj


@router.post("", response_model=EquipamentoOut, status_code=status.HTTP_201_CREATED)
def criar(dados: EquipamentoCreate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = Equipamento(**dados.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{item_id}", response_model=EquipamentoOut)
def atualizar(item_id: int, dados: EquipamentoUpdate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(Equipamento).filter(Equipamento.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    for chave, valor in dados.model_dump(exclude_unset=True).items():
        setattr(obj, chave, valor)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(Equipamento).filter(Equipamento.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    excluir_protegido(db, obj)
