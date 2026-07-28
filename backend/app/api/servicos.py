from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.models import Usuario, Servico
from app.api.deps import get_current_usuario, require_funcao
from app.schemas.servico import ServicoOut, ServicoCreate, ServicoUpdate

router = APIRouter(prefix="/servicos", tags=["servicos"])
_escrita = require_funcao("Comercial Pós-Vendas", "Administrador", "Financeiro")


@router.get("", response_model=list[ServicoOut])
def listar(q: str | None = None, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    query = db.query(Servico)
    if q:
        query = query.filter(Servico.nome.ilike(f"%{q}%") | Servico.sku.ilike(f"%{q}%"))
    return query.order_by(Servico.nome).all()


@router.post("", response_model=ServicoOut, status_code=status.HTTP_201_CREATED)
def criar(dados: ServicoCreate, db: Session = Depends(get_db), _: Usuario = Depends(_escrita)):
    obj = Servico(**dados.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.patch("/{item_id}", response_model=ServicoOut)
def atualizar(item_id: int, dados: ServicoUpdate, db: Session = Depends(get_db), _: Usuario = Depends(_escrita)):
    obj = db.query(Servico).filter(Servico.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    for chave, valor in dados.model_dump(exclude_unset=True).items():
        setattr(obj, chave, valor)
    db.commit(); db.refresh(obj)
    return obj


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(_escrita)):
    obj = db.query(Servico).filter(Servico.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    db.delete(obj); db.commit()
