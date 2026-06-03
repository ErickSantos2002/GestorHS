from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Ordem, Fase, LogOS, Usuario

ADMIN = "Administrador"


def agora() -> datetime:
    return datetime.now(timezone.utc)


def exige_funcao_da_fase(db: Session, usuario: Usuario, fase_id: int) -> None:
    """403 se o usuário não for Admin nem a função responsável pela fase atual."""
    if usuario.funcao == ADMIN:
        return
    fase = db.query(Fase).filter(Fase.id == fase_id).first()
    if fase is None or fase.funcao_responsavel is None or usuario.funcao_id != fase.funcao_responsavel:
        raise HTTPException(status_code=403, detail="Acesso negado para sua função nesta fase")


def registrar_log(db: Session, ordem: Ordem, usuario: Usuario | None, texto: str) -> None:
    db.add(LogOS(os=ordem.id, usuario=usuario.id if usuario else None, datalog=agora(), autor="1", texto=texto))
