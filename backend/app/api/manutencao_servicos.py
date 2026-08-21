"""Catalogo de servicos de manutencao.

Lista FECHADA: o relatorio so aceita servico daqui. Padroniza a escrita do
documento e deixa o dado pronto para responder "qual defeito mais aparece".

Escrita com Laboratorio e Administrador — se so o Administrador cadastrasse, o
tecnico ficaria travado ao encontrar um defeito novo. Excluir segue so com o
Administrador, como nos cilindros de gas.
"""
from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import ADMIN, get_current_usuario, require_funcao
from app.models import ManutencaoServico, Usuario
from app.models.database import get_db
from app.schemas.manutencao import ServicoIn, ServicoOut, ServicoUpdate

router = APIRouter(prefix="/manutencao-servicos", tags=["manutencao"])

_escrita = require_funcao(ADMIN, "Laboratório")
_excluir = require_funcao(ADMIN)


def _ou_404(db: Session, servico_id: int) -> ManutencaoServico:
    s = db.query(ManutencaoServico).filter(ManutencaoServico.id == servico_id).first()
    if s is None:
        raise HTTPException(404, "serviço não encontrado")
    return s


@router.get("", response_model=list[ServicoOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(get_current_usuario)):
    return db.query(ManutencaoServico).order_by(ManutencaoServico.descricao).all()


@router.post("", response_model=ServicoOut, status_code=http_status.HTTP_201_CREATED)
def criar(dados: ServicoIn, db: Session = Depends(get_db), _: Usuario = Depends(_escrita)):
    s = ManutencaoServico(descricao=dados.descricao.strip(),
                          resumo_padrao=dados.resumo_padrao.strip(), ativo=dados.ativo)
    db.add(s)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "já existe um serviço com essa descrição")
    db.refresh(s)
    return s


@router.put("/{servico_id}", response_model=ServicoOut)
def atualizar(servico_id: int, dados: ServicoUpdate, db: Session = Depends(get_db),
              _: Usuario = Depends(_escrita)):
    s = _ou_404(db, servico_id)
    campos = dados.model_dump(exclude_unset=True)
    for chave, valor in campos.items():
        setattr(s, chave, valor.strip() if isinstance(valor, str) else valor)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "já existe um serviço com essa descrição")
    db.refresh(s)
    return s


@router.delete("/{servico_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def excluir(servico_id: int, db: Session = Depends(get_db), _: Usuario = Depends(_excluir)):
    s = _ou_404(db, servico_id)
    db.delete(s)
    try:
        db.commit()
    except IntegrityError:
        # Servico ja usado em relatorio emitido: desativar em vez de apagar,
        # senao o relatorio perde o registro do que foi feito.
        db.rollback()
        raise HTTPException(409, "este serviço já foi usado em um relatório — desative em vez de excluir")
