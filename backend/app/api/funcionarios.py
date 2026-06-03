from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Cliente, Funcionario
from app.api.deps import get_current_usuario, require_funcao
from app.schemas.clientes import FuncionarioOut, FuncionarioCreate, FuncionarioUpdate

router = APIRouter(tags=["funcionarios"])
ADMIN = "Administrador"


def _exige_cliente(db: Session, cliente_id: int) -> None:
    if db.query(Cliente).filter(Cliente.id == cliente_id).first() is None:
        raise HTTPException(status_code=404, detail="cliente não encontrado")


@router.get("/clientes/{cliente_id}/funcionarios", response_model=list[FuncionarioOut])
def listar(cliente_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    _exige_cliente(db, cliente_id)
    return db.query(Funcionario).filter(Funcionario.cliente == cliente_id).order_by(Funcionario.id).all()


@router.post("/clientes/{cliente_id}/funcionarios", response_model=FuncionarioOut, status_code=status.HTTP_201_CREATED)
def criar(cliente_id: int, dados: FuncionarioCreate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    _exige_cliente(db, cliente_id)
    obj = Funcionario(cliente=cliente_id, **dados.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/funcionarios/{item_id}", response_model=FuncionarioOut)
def atualizar(item_id: int, dados: FuncionarioUpdate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(Funcionario).filter(Funcionario.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    for chave, valor in dados.model_dump(exclude_unset=True).items():
        setattr(obj, chave, valor)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/funcionarios/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(Funcionario).filter(Funcionario.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    db.delete(obj)
    db.commit()
