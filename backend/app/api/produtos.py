from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.models import Usuario, Produto
from app.api.deps import get_current_usuario, require_funcao
from app.schemas.produto import ProdutoOut, ProdutoCreate, ProdutoUpdate

router = APIRouter(prefix="/produtos", tags=["produtos"])
_escrita = require_funcao("Comercial Pós-Vendas", "Administrador")


@router.get("", response_model=list[ProdutoOut])
def listar(q: str | None = None, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    query = db.query(Produto)
    if q:
        query = query.filter(Produto.nome.ilike(f"%{q}%") | Produto.sku.ilike(f"%{q}%"))
    return query.order_by(Produto.nome).all()


@router.post("", response_model=ProdutoOut, status_code=status.HTTP_201_CREATED)
def criar(dados: ProdutoCreate, db: Session = Depends(get_db), _: Usuario = Depends(_escrita)):
    obj = Produto(**dados.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.patch("/{item_id}", response_model=ProdutoOut)
def atualizar(item_id: int, dados: ProdutoUpdate, db: Session = Depends(get_db), _: Usuario = Depends(_escrita)):
    obj = db.query(Produto).filter(Produto.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    for chave, valor in dados.model_dump(exclude_unset=True).items():
        setattr(obj, chave, valor)
    db.commit(); db.refresh(obj)
    return obj


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(_escrita)):
    obj = db.query(Produto).filter(Produto.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    db.delete(obj); db.commit()
