import re

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Cliente
from app.api.deps import get_current_usuario, require_funcao, GESTOR_CADASTRO, EDITOR_CADASTRO
from app.api.cadastros_common import excluir_protegido
from app.api.exportar_common import resposta_xlsx
from app.core.exportacoes import COLUNAS_CLIENTES, linha_cliente
from app.schemas.clientes import ClienteListOut, ClientesPage, ClienteOut, ClienteCreate, ClienteUpdate

router = APIRouter(prefix="/clientes", tags=["clientes"])
ADMIN = "Administrador"


def _query_clientes(db: Session, q: str | None = None):
    """Filtros da lista de clientes. Usado por listar() e por exportar() —
    ter um lugar so' impede que a planilha ignore um filtro novo em silencio."""
    query = db.query(Cliente)
    if q:
        termo = f"%{q}%"
        filtros = [Cliente.nome.ilike(termo), Cliente.municipio.ilike(termo)]
        digitos = re.sub(r"\D", "", q)
        if digitos:
            termo_doc = f"%{digitos}%"
            filtros += [Cliente.cgc.ilike(termo_doc), Cliente.cpf.ilike(termo_doc)]
        query = query.filter(or_(*filtros))
    return query.order_by(Cliente.nome)


@router.get("", response_model=ClientesPage)
def listar(
    q: str | None = None,
    offset: int = 0,
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    query = _query_clientes(db, q=q)
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return ClientesPage(items=[ClienteListOut.model_validate(c) for c in items], total=total)


@router.get("/exportar")
def exportar(
    q: str | None = None,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    itens = _query_clientes(db, q=q).all()
    return resposta_xlsx(
        "clientes", "Clientes", COLUNAS_CLIENTES,
        [linha_cliente(c) for c in itens], {"Busca": q},
    )


@router.get("/{cliente_id}", response_model=ClienteOut)
def obter(cliente_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    obj = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    return obj


@router.post("", response_model=ClienteOut, status_code=status.HTTP_201_CREATED)
def criar(dados: ClienteCreate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(*GESTOR_CADASTRO))):
    obj = Cliente(**dados.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{cliente_id}", response_model=ClienteOut)
def atualizar(cliente_id: int, dados: ClienteUpdate, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(*EDITOR_CADASTRO))):
    obj = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    for chave, valor in dados.model_dump(exclude_unset=True).items():
        setattr(obj, chave, valor)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{cliente_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(cliente_id: int, db: Session = Depends(get_db), _: Usuario = Depends(require_funcao(ADMIN))):
    obj = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail="não encontrado")
    excluir_protegido(db, obj)
