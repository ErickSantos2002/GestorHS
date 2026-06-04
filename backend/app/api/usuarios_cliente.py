from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Cliente, UsuarioCliente
from app.api.deps import require_funcao
from app.core.security import hash_senha
from app.schemas.usuarios_cliente import (
    UsuarioPortalOut, UsuarioPortalCreate, UsuarioPortalUpdate, RedefinirSenhaClienteIn,
)

router = APIRouter(tags=["usuarios-portal"])
ADMIN = "Administrador"


def _exige_cliente(db: Session, cliente_id: int) -> None:
    if db.query(Cliente).filter(Cliente.id == cliente_id).first() is None:
        raise HTTPException(status_code=404, detail="cliente não encontrado")


@router.get("/clientes/{cliente_id}/usuarios-portal", response_model=list[UsuarioPortalOut])
def listar(cliente_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    _exige_cliente(db, cliente_id)
    return db.query(UsuarioCliente).filter(UsuarioCliente.cliente == cliente_id).order_by(UsuarioCliente.id).all()


@router.post("/clientes/{cliente_id}/usuarios-portal", response_model=UsuarioPortalOut, status_code=status.HTTP_201_CREATED)
def criar(cliente_id: int, dados: UsuarioPortalCreate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    _exige_cliente(db, cliente_id)
    existe = (
        db.query(UsuarioCliente)
        .filter(UsuarioCliente.cliente == cliente_id, UsuarioCliente.login == dados.login)
        .first()
    )
    if existe is not None:
        raise HTTPException(status_code=409, detail="login já em uso para este cliente")
    obj = UsuarioCliente(
        cliente=cliente_id, login=dados.login, nome=dados.nome, email=dados.email,
        senha=hash_senha(dados.senha), precisa_redefinir_senha=True,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/usuarios-portal/{item_id}", response_model=UsuarioPortalOut)
def atualizar(item_id: int, dados: UsuarioPortalUpdate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(UsuarioCliente).filter(UsuarioCliente.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    campos = dados.model_dump(exclude_unset=True)
    if "login" in campos and campos["login"] != obj.login:
        dup = (
            db.query(UsuarioCliente)
            .filter(UsuarioCliente.cliente == obj.cliente, UsuarioCliente.login == campos["login"])
            .first()
        )
        if dup is not None:
            raise HTTPException(status_code=409, detail="login já em uso para este cliente")
    for chave, valor in campos.items():
        setattr(obj, chave, valor)
    db.commit()
    db.refresh(obj)
    return obj


@router.post("/usuarios-portal/{item_id}/redefinir-senha", status_code=status.HTTP_204_NO_CONTENT)
def redefinir_senha(item_id: int, dados: RedefinirSenhaClienteIn, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(UsuarioCliente).filter(UsuarioCliente.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    obj.senha = hash_senha(dados.nova_senha)
    obj.precisa_redefinir_senha = True
    db.commit()


@router.delete("/usuarios-portal/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(UsuarioCliente).filter(UsuarioCliente.id == item_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    db.delete(obj)
    db.commit()
