from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Funcao
from app.core.security import hash_senha
from app.core import emails
from app.api.deps import require_funcao
from app.schemas.acesso import UsuarioListOut, UsuarioCreate, UsuarioUpdate, RedefinirSenhaIn

router = APIRouter(prefix="/usuarios", tags=["usuarios"])

ADMIN = "Administrador"


def _conta_admins(db: Session) -> int:
    return (
        db.query(Usuario)
        .join(Funcao, Usuario.funcao_id == Funcao.id)
        .filter(Funcao.descricao == ADMIN, Usuario.ativo.is_(True))
        .count()
    )


def _eh_admin(usuario: Usuario) -> bool:
    return usuario.funcao_rel is not None and usuario.funcao_rel.descricao == ADMIN


@router.get("", response_model=list[UsuarioListOut])
def listar(incluir_inativos: bool = False, db: Session = Depends(get_db),
           _: Usuario = Depends(require_funcao(ADMIN))):
    query = db.query(Usuario)
    if not incluir_inativos:
        query = query.filter(Usuario.ativo.is_(True))
    return query.order_by(Usuario.id).all()


@router.post("", response_model=UsuarioListOut, status_code=status.HTTP_201_CREATED)
def criar(dados: UsuarioCreate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    email = emails.normalizar(dados.email)
    if db.query(Usuario).filter(Usuario.email == email).first() is not None:
        raise HTTPException(status_code=409, detail="e-mail já em uso")
    u = Usuario(
        nome=dados.nome,
        email=email,
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
    if "email" in campos:
        if campos["email"] is None:
            raise HTTPException(status_code=422, detail="e-mail é obrigatório")
        campos["email"] = emails.normalizar(campos["email"])
        if campos["email"] != u.email:
            if db.query(Usuario).filter(Usuario.email == campos["email"]).first() is not None:
                raise HTTPException(status_code=409, detail="e-mail já em uso")
    if "funcao_id" in campos and campos["funcao_id"] != u.funcao_id and _eh_admin(u):
        if _conta_admins(db) <= 1:
            raise HTTPException(status_code=400, detail="não é possível remover o último administrador")
    for chave, valor in campos.items():
        setattr(u, chave, valor)
    db.commit()
    db.refresh(u)
    return u


@router.post("/{usuario_id}/desativar", status_code=status.HTTP_204_NO_CONTENT)
def desativar(usuario_id: int, db: Session = Depends(get_db),
              atual: Usuario = Depends(require_funcao(ADMIN))):
    u = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if u is None:
        raise HTTPException(status_code=404, detail="usuário não encontrado")
    if u.id == atual.id:
        raise HTTPException(status_code=400, detail="não é possível desativar o próprio usuário")
    if not u.ativo:
        return  # idempotente
    if _eh_admin(u) and _conta_admins(db) <= 1:
        raise HTTPException(status_code=400, detail="não é possível desativar o último administrador")
    u.ativo = False
    db.commit()


@router.post("/{usuario_id}/reativar", status_code=status.HTTP_204_NO_CONTENT)
def reativar(usuario_id: int, db: Session = Depends(get_db),
             _: Usuario = Depends(require_funcao(ADMIN))):
    u = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if u is None:
        raise HTTPException(status_code=404, detail="usuário não encontrado")
    u.ativo = True
    db.commit()


@router.post("/{usuario_id}/redefinir-senha", status_code=status.HTTP_204_NO_CONTENT)
def redefinir_senha(usuario_id: int, dados: RedefinirSenhaIn, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    u = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if u is None:
        raise HTTPException(status_code=404, detail="usuário não encontrado")
    u.senha = hash_senha(dados.nova_senha)
    u.precisa_redefinir_senha = True
    db.commit()
