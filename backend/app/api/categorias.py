from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Categoria
from app.api.deps import get_current_usuario, require_funcao
from app.api.cadastros_common import excluir_protegido
from app.schemas.cadastros import CategoriaOut, CategoriaCreate, CategoriaUpdate

router = APIRouter(prefix="/categorias", tags=["categorias"])
ADMIN = "Administrador"


@router.get("", response_model=list[CategoriaOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    return db.query(Categoria).order_by(Categoria.posicao, Categoria.id).all()


@router.get("/{item_id}", response_model=CategoriaOut)
def obter(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    obj = db.query(Categoria).filter(Categoria.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    return obj


@router.post("", response_model=CategoriaOut, status_code=status.HTTP_201_CREATED)
def criar(dados: CategoriaCreate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = Categoria(descricao=dados.descricao, setor=dados.setor, posicao=dados.posicao)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{item_id}", response_model=CategoriaOut)
def atualizar(item_id: int, dados: CategoriaUpdate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(Categoria).filter(Categoria.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    for chave, valor in dados.model_dump(exclude_unset=True).items():
        setattr(obj, chave, valor)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(Categoria).filter(Categoria.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    excluir_protegido(db, obj)
