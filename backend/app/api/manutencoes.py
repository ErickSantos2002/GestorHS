"""Registro da manutencao feita na bancada.

Uma por OS (unicidade em `manutencoes.os`), com N servicos do catalogo dentro.
Janela 5-8, a mesma do certificado de calibracao, que permite regerar OS antiga
sob demanda — antes do laboratorio nao ha o que registrar.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import ADMIN, get_current_usuario, require_funcao
from app.core.manutencao import compor_resumo
from app.models import Manutencao, ManutencaoItem, ManutencaoServico, Ordem, Usuario
from app.models.database import get_db
from app.schemas.manutencao import ManutencaoIn, ManutencaoItemOut, ManutencaoOut

router = APIRouter(tags=["manutencao"])

_escrita = require_funcao(ADMIN, "Laboratório")

# Do Laboratorio ate Finalizada. Cancelada (9) e Recebido (4) ficam de fora.
FASES_PERMITIDAS = (5, 6, 7, 8)


def _os_ou_404(db: Session, ordem_id: int) -> Ordem:
    o = db.query(Ordem).filter(Ordem.id == ordem_id).first()
    if o is None:
        raise HTTPException(404, "OS não encontrada")
    return o


def manutencao_da_os(db: Session, ordem_id: int) -> Manutencao | None:
    """Usado tambem pela geracao do certificado (certificados_os)."""
    return db.query(Manutencao).filter(Manutencao.os == ordem_id).first()


def _saida(m: Manutencao) -> ManutencaoOut:
    return ManutencaoOut(
        id=m.id, os=m.os, numero=m.numero, data_manutencao=m.data_manutencao, resumo=m.resumo,
        servicos=[ManutencaoItemOut(servico=i.servico, descricao=i.servico_rel.descricao,
                                    resumo_padrao=i.servico_rel.resumo_padrao)
                  for i in m.itens],
    )


@router.get("/ordens/{ordem_id}/manutencao", response_model=ManutencaoOut)
def obter(ordem_id: int, db: Session = Depends(get_db),
          _: Usuario = Depends(get_current_usuario)):
    _os_ou_404(db, ordem_id)
    m = manutencao_da_os(db, ordem_id)
    if m is None:
        raise HTTPException(404, "esta OS não tem manutenção registrada")
    return _saida(m)


@router.put("/ordens/{ordem_id}/manutencao", response_model=ManutencaoOut)
def registrar(ordem_id: int, dados: ManutencaoIn, db: Session = Depends(get_db),
              usuario: Usuario = Depends(_escrita)):
    ordem = _os_ou_404(db, ordem_id)
    if ordem.fase not in FASES_PERMITIDAS:
        raise HTTPException(409, "a manutenção só pode ser registrada do Laboratório em diante")

    servicos = []
    for sid in dados.servicos:
        s = db.query(ManutencaoServico).filter(ManutencaoServico.id == sid).first()
        if s is None:
            raise HTTPException(422, f"serviço {sid} não existe no catálogo")
        servicos.append(s)

    m = manutencao_da_os(db, ordem_id)
    if m is None:
        m = Manutencao(os=ordem_id, criado_por=usuario.nome)
        db.add(m)
    m.numero = dados.numero
    m.data_manutencao = dados.data_manutencao
    # A composicao tem dono no servidor: se o resumo nao vier preenchido e
    # houver servicos, compoe a partir das frases padrao do catalogo — a tela
    # so faz preview, quem decide o texto final e' a API.
    if (not dados.resumo or not dados.resumo.strip()) and servicos:
        m.resumo = compor_resumo([s.resumo_padrao for s in servicos])
    else:
        m.resumo = dados.resumo
    m.atualizado_em = datetime.now(timezone.utc)
    db.flush()

    # Substitui a lista inteira: e' o jeito de refletir remocao e reordenacao
    # sem precisar diferenciar item a item.
    m.itens.clear()
    db.flush()
    for posicao, s in enumerate(servicos):
        db.add(ManutencaoItem(manutencao=m.id, servico=s.id, ordem=posicao))
    db.commit()
    db.refresh(m)
    return _saida(m)
