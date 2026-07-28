"""Endpoints REST de Propostas Técnicas: CRUD + PDF (atual e por versão) +
duplicar. Camada fina sobre `core/proposta_servico.py` (numeração, totais,
versionamento) e `core/proposta_pdf.py` (geração/arquivamento de PDF via
Playwright) — sem regra de negócio aqui, só orquestração HTTP.
"""
import re
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import Usuario, Cliente, Proposta, PropostaVersao
from app.api.deps import get_current_usuario, require_funcao
from app.core import proposta_servico as ps
from app.core import proposta_pdf
from app.schemas.proposta import (
    PropostaCreate, PropostaUpdate, PropostaOut, PropostaListOut, PropostaVersaoOut,
    PropostaItemCreate, PropostaAparelhoCreate,
)

router = APIRouter(prefix="/propostas", tags=["propostas"])

# Quem pode criar/alterar/excluir/duplicar propostas.
_escrever = require_funcao("Comercial Pós-Vendas", "Administrador", "Financeiro")


def _proposta_ou_404(db: Session, proposta_id: int) -> Proposta:
    proposta = (
        db.query(Proposta)
        .filter(Proposta.id == proposta_id, Proposta.is_deleted.is_(False))
        .first()
    )
    if proposta is None:
        raise HTTPException(status_code=404, detail="Proposta não encontrada")
    return proposta


def _content_disposition(download: int, filename: str) -> str:
    tipo = "attachment" if download else "inline"
    return f'{tipo}; filename="{filename}"'


# ---------------------------------------------------------------------------
# Listar / criar
# ---------------------------------------------------------------------------

@router.get("", response_model=PropostaListOut)
def listar(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str | None = None,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    query = db.query(Proposta).filter(Proposta.is_deleted.is_(False))
    if q:
        qs = q.strip()
        termo = f"%{qs}%"
        filtros = [Cliente.nome.ilike(termo)]
        digitos = re.sub(r"\D", "", qs)
        if digitos and (not qs.isdigit() or len(digitos) >= 11):
            termo_doc = f"%{digitos}%"
            filtros += [Cliente.cgc.ilike(termo_doc), Cliente.cpf.ilike(termo_doc)]
        if qs.isdigit():
            filtros.append(Proposta.numero == int(qs))
        query = query.outerjoin(Cliente, Proposta.cliente == Cliente.id).filter(or_(*filtros))

    total = query.count()
    total_pages = (total + page_size - 1) // page_size
    itens = (
        query.order_by(Proposta.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PropostaListOut(
        items=[ps.montar_saida(db, p) for p in itens],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("", response_model=PropostaOut, status_code=status.HTTP_201_CREATED)
def criar(
    dados: PropostaCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_escrever),
):
    proposta = ps.criar_proposta(db, dados, vendedor=usuario.nome)
    return ps.montar_saida(db, proposta)


# ---------------------------------------------------------------------------
# Sub-rotas de {proposta_id} — precisam vir ANTES de GET/PUT/DELETE /{proposta_id}
# (senão o FastAPI casa "pdf"/"versoes"/"duplicar" como valor do path param).
# ---------------------------------------------------------------------------

@router.get("/{proposta_id}/pdf")
def pdf(
    proposta_id: int,
    download: int = 0,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    _proposta_ou_404(db, proposta_id)
    try:
        conteudo = proposta_pdf.gerar_pdf(db, proposta_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Proposta não encontrada")
    return Response(
        content=conteudo,
        media_type="application/pdf",
        headers={"Content-Disposition": _content_disposition(download, f"proposta-{proposta_id}.pdf")},
    )


@router.get("/{proposta_id}/versoes", response_model=list[PropostaVersaoOut])
def versoes(
    proposta_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    _proposta_ou_404(db, proposta_id)
    registros = (
        db.query(PropostaVersao)
        .filter(PropostaVersao.proposta == proposta_id)
        .order_by(PropostaVersao.numero_versao.desc())
        .all()
    )
    saida = []
    for v in registros:
        item = PropostaVersaoOut.model_validate(v)
        item.has_pdf = bool(v.pdf_path)
        saida.append(item)
    return saida


@router.get("/{proposta_id}/versoes/{versao_id}/pdf")
def versao_pdf(
    proposta_id: int,
    versao_id: int,
    download: int = 0,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    _proposta_ou_404(db, proposta_id)
    v = (
        db.query(PropostaVersao)
        .filter(PropostaVersao.id == versao_id, PropostaVersao.proposta == proposta_id)
        .first()
    )
    if v is None:
        raise HTTPException(status_code=404, detail="Versão não encontrada")
    try:
        conteudo = proposta_pdf.ler_pdf_versao(v.pdf_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    nome = f"proposta-{proposta_id}-v{v.numero_versao}.pdf"
    return Response(
        content=conteudo,
        media_type="application/pdf",
        headers={"Content-Disposition": _content_disposition(download, nome)},
    )


@router.post("/{proposta_id}/duplicar", response_model=PropostaOut, status_code=status.HTTP_201_CREATED)
def duplicar(
    proposta_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_escrever),
):
    """Clona a proposta original com número novo, mesmos itens/aparelhos/campos,
    `data` de hoje e `vendedor` = quem duplicou. Não copia versões — a nova
    proposta nasce sem histórico."""
    original = _proposta_ou_404(db, proposta_id)
    dados = PropostaCreate(
        cliente=original.cliente,
        contato=original.contato,
        vendedor=usuario.nome,
        data=date.today(),
        intro=original.intro,
        outros_itens=original.outros_itens,
        desconto=float(original.desconto or 0),
        frete=float(original.frete or 0),
        forma_envio=original.forma_envio,
        forma_frete=original.forma_frete,
        transportador=original.transportador,
        condicao_pagamento=original.condicao_pagamento,
        validade_dias=original.validade_dias,
        data_entrega=original.data_entrega,
        descricao_entrega=original.descricao_entrega,
        endereco_entrega_diferente=original.endereco_entrega_diferente,
        endereco_entrega=original.endereco_entrega,
        cliente_override=original.cliente_override,
        observacoes=original.observacoes,
        assinatura=original.assinatura,
        itens=[
            PropostaItemCreate(
                descricao=i.descricao, sku=i.sku, quantidade=float(i.quantidade),
                unidade=i.unidade, preco_un=float(i.preco_un),
            )
            for i in original.itens
        ],
        aparelhos=[
            PropostaAparelhoCreate(equipamento_cliente=a.equipamento_cliente)
            for a in original.aparelhos if a.equipamento_cliente is not None
        ],
    )
    nova = ps.criar_proposta(db, dados, vendedor=usuario.nome)
    return ps.montar_saida(db, nova)


# ---------------------------------------------------------------------------
# CRUD por id
# ---------------------------------------------------------------------------

@router.get("/{proposta_id}", response_model=PropostaOut)
def obter(
    proposta_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_usuario),
):
    proposta = _proposta_ou_404(db, proposta_id)
    return ps.montar_saida(db, proposta)


@router.put("/{proposta_id}", response_model=PropostaOut)
def atualizar(
    proposta_id: int,
    dados: PropostaUpdate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_escrever),
):
    proposta = _proposta_ou_404(db, proposta_id)
    atualizado = ps.atualizar_proposta(db, proposta, dados, alterado_por=usuario.nome)
    return ps.montar_saida(db, atualizado)


@router.delete("/{proposta_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(
    proposta_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(_escrever),
):
    proposta = _proposta_ou_404(db, proposta_id)
    proposta.is_deleted = True
    proposta.deleted_at = datetime.now(timezone.utc)
    db.commit()
