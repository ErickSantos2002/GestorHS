from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Funcao
from app.api.deps import require_funcao
from app.api.cadastros_common import excluir_protegido
from app.schemas.acesso import FuncaoOut
from app.schemas.fases import FuncaoCreate, FuncaoUpdate

router = APIRouter(prefix="/funcoes", tags=["funcoes"])
ADMIN = "Administrador"


@router.get("", response_model=list[FuncaoOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    return db.query(Funcao).order_by(Funcao.id).all()


@router.post("", response_model=FuncaoOut, status_code=http_status.HTTP_201_CREATED)
def criar(dados: FuncaoCreate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    if db.query(Funcao).filter(Funcao.descricao == dados.descricao).first() is not None:
        raise HTTPException(status_code=409, detail="função já existe")
    obj = Funcao(descricao=dados.descricao)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{funcao_id}", response_model=FuncaoOut)
def atualizar(funcao_id: int, dados: FuncaoUpdate, db: Session = Depends(get_db),
              _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(Funcao).filter(Funcao.id == funcao_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrada")
    existe = db.query(Funcao).filter(Funcao.descricao == dados.descricao, Funcao.id != funcao_id).first()
    if existe is not None:
        raise HTTPException(status_code=409, detail="função já existe")
    obj.descricao = dados.descricao
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{funcao_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def excluir(funcao_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(Funcao).filter(Funcao.id == funcao_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrada")
    excluir_protegido(db, obj)
