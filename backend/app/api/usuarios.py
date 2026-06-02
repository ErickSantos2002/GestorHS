from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Funcao
from app.core.security import hash_senha
from app.api.deps import require_funcao
from app.schemas.acesso import UsuarioListOut, UsuarioCreate, UsuarioUpdate

router = APIRouter(prefix="/usuarios", tags=["usuarios"])

ADMIN = "Administrador"


def _conta_admins(db: Session) -> int:
    return (
        db.query(Usuario)
        .join(Funcao, Usuario.funcao_id == Funcao.id)
        .filter(Funcao.descricao == ADMIN)
        .count()
    )


def _eh_admin(db: Session, usuario: Usuario) -> bool:
    if usuario.funcao_id is None:
        return False
    f = db.query(Funcao).filter(Funcao.id == usuario.funcao_id).first()
    return f is not None and f.descricao == ADMIN


@router.get("", response_model=list[UsuarioListOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    return db.query(Usuario).order_by(Usuario.id).all()


@router.post("", response_model=UsuarioListOut, status_code=status.HTTP_201_CREATED)
def criar(dados: UsuarioCreate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    if db.query(Usuario).filter(Usuario.login == dados.login).first() is not None:
        raise HTTPException(status_code=409, detail="login já em uso")
    u = Usuario(
        nome=dados.nome,
        login=dados.login,
        email=dados.email,
        senha=hash_senha(dados.senha),
        funcao_id=dados.funcao_id,
        precisa_redefinir_senha=False,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@router.get("/{usuario_id}", response_model=UsuarioListOut)
def obter(usuario_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    u = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if u is None:
        raise HTTPException(status_code=404, detail="usuário não encontrado")
    return u


@router.patch("/{usuario_id}", response_model=UsuarioListOut)
def atualizar(usuario_id: int, dados: UsuarioUpdate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    u = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if u is None:
        raise HTTPException(status_code=404, detail="usuário não encontrado")
    campos = dados.model_dump(exclude_unset=True)
    if "login" in campos and campos["login"] != u.login:
        if db.query(Usuario).filter(Usuario.login == campos["login"]).first() is not None:
            raise HTTPException(status_code=409, detail="login já em uso")
    if "funcao_id" in campos and campos["funcao_id"] != u.funcao_id and _eh_admin(db, u):
        if _conta_admins(db) <= 1:
            raise HTTPException(status_code=400, detail="não é possível remover o último administrador")
    for chave, valor in campos.items():
        setattr(u, chave, valor)
    db.commit()
    db.refresh(u)
    return u
