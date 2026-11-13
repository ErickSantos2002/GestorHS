"""GET /agente/capacidades: o que o Guardi alcanca no GestorHS com o login do dono.

So para token de agente (login normal -> 404). A resposta sai de
core/agente.FUNCOES_DAS_ESCRITAS, tabela presa ao require_funcao de cada rota por
test_agente_capacidades.py. Spec: HS.OS/docs/superpowers/specs/
2026-11-13-capacidade-do-guardi-design.md
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import ADMIN, eh_agente, get_current_usuario
from app.core import os_workflow as wf
from app.core.agente import rotas_do_login
from app.models import Fase, Usuario
from app.models.database import get_db

router = APIRouter(prefix="/agente", tags=["agente"])

# Fases de onde a caixa sai por /avancar, nas duas rotas (normal e so Modulo).
_FASES_COM_SAIDA = frozenset(wf.PROXIMA) | frozenset(wf.PROXIMA_SO_MODULO)


def _avanca_alguma_fase(db: Session, usuario: Usuario) -> bool:
    """Mesma regra de exige_funcao_da_fase, perguntada para TODAS as fases com saida."""
    if usuario.funcao == ADMIN:
        return True
    if usuario.funcao_id is None:
        return False
    return db.query(Fase.id).filter(
        Fase.id.in_(_FASES_COM_SAIDA), Fase.funcao_responsavel == usuario.funcao_id,
    ).first() is not None


@router.get("/capacidades")
def capacidades(request: Request, db: Session = Depends(get_db),
                usuario: Usuario = Depends(get_current_usuario)) -> dict:
    if not eh_agente(request):
        raise HTTPException(status_code=404, detail="Not Found")
    return {
        "papel": usuario.funcao or "Sem função",
        "rotas": rotas_do_login(usuario.funcao, _avanca_alguma_fase(db, usuario)),
    }
