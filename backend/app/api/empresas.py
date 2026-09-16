"""Cadastro de Empresas (filiais). Camada fina sobre core/empresa_servico.py."""
import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_usuario, require_funcao
from app.core import empresa_servico as es
from app.core.empresa import DocumentoInvalido
from app.models import Empresa, Usuario
from app.models.database import get_db
from app.schemas.empresa import EmpresaIn, EmpresaOut, EmpresasPage

router = APIRouter(prefix="/empresas", tags=["empresas"])

# Mesmo trio de quem faz proposta: o modal da proposta cria e edita Empresa.
_escrever = require_funcao("Comercial Pós-Vendas", "Financeiro", "Administrador")


def _empresa_ou_404(db: Session, empresa_id: int) -> Empresa:
    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    return empresa


def _gravar(db: Session, empresa: Empresa) -> EmpresaOut:
    """Commit traduzindo a corrida de dois POST com o mesmo documento: o indice
    unico estoura aqui depois de a checagem ter passado nos dois."""
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Documento já cadastrado")
    db.refresh(empresa)
    return es.saida_empresa(empresa)


def _executar(db: Session, fn, *args):
    try:
        return fn(db, *args)
    except (DocumentoInvalido, es.MatrizInexistente) as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except es.DocumentoDuplicado as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))


@router.get("", response_model=EmpresasPage)
def listar(
    q: str | None = None,
    cliente: int | None = None,
    ativo: bool | None = None,
    offset: int = 0,
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    query = db.query(Empresa)
    if q:
        termo = f"%{q.strip()}%"
        filtros = [Empresa.nome.ilike(termo), Empresa.municipio.ilike(termo)]
        digitos = re.sub(r"\D", "", q)
        if digitos:
            filtros += [Empresa.cgc.ilike(f"%{digitos}%"), Empresa.cpf.ilike(f"%{digitos}%")]
        query = query.filter(or_(*filtros))
    if cliente is not None:
        query = query.filter(Empresa.cliente == cliente)
    if ativo is not None:
        query = query.filter(Empresa.ativo.is_(ativo))
    total = query.count()
    itens = query.order_by(Empresa.nome).offset(offset).limit(limit).all()
    return EmpresasPage(items=[es.saida_empresa(e) for e in itens], total=total)


@router.get("/{empresa_id}", response_model=EmpresaOut)
def obter(empresa_id: int, db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    return es.saida_empresa(_empresa_ou_404(db, empresa_id))


@router.post("", response_model=EmpresaOut, status_code=status.HTTP_201_CREATED)
def criar(dados: EmpresaIn, db: Session = Depends(get_db), _: Usuario = Depends(_escrever)):
    empresa = _executar(db, es.criar_empresa, dados)
    return _gravar(db, empresa)


@router.put("/{empresa_id}", response_model=EmpresaOut)
def atualizar(empresa_id: int, dados: EmpresaIn, db: Session = Depends(get_db), _: Usuario = Depends(_escrever)):
    empresa = _empresa_ou_404(db, empresa_id)
    _executar(db, es.atualizar_empresa, empresa, dados)
    return _gravar(db, empresa)


@router.post("/{empresa_id}/desativar", response_model=EmpresaOut)
def desativar(empresa_id: int, db: Session = Depends(get_db), _: Usuario = Depends(_escrever)):
    empresa = _empresa_ou_404(db, empresa_id)
    empresa.ativo = False
    return _gravar(db, empresa)


@router.post("/{empresa_id}/reativar", response_model=EmpresaOut)
def reativar(empresa_id: int, db: Session = Depends(get_db), _: Usuario = Depends(_escrever)):
    empresa = _empresa_ou_404(db, empresa_id)
    empresa.ativo = True
    return _gravar(db, empresa)
