from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Setor
from app.api.deps import get_current_usuario, require_funcao
from app.api.cadastros_common import excluir_protegido
from app.schemas.cadastros import SetorOut, SetorCreate, SetorUpdate

router = APIRouter(prefix="/setores", tags=["setores"])
ADMIN = "Administrador"


@router.get("", response_model=list[SetorOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    return db.query(Setor).order_by(Setor.id).all()


@router.get("/{item_id}", response_model=SetorOut)
def obter(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    obj = db.query(Setor).filter(Setor.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    return obj


@router.post("", response_model=SetorOut, status_code=status.HTTP_201_CREATED)
def criar(dados: SetorCreate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = Setor(descricao=dados.descricao)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{item_id}", response_model=SetorOut)
def atualizar(item_id: int, dados: SetorUpdate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(Setor).filter(Setor.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    for chave, valor in dados.model_dump(exclude_unset=True).items():
        setattr(obj, chave, valor)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(Setor).filter(Setor.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    excluir_protegido(db, obj)
