from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def excluir_protegido(db: Session, obj) -> None:
    """Exclui o objeto; se houver FK referenciando-o, devolve 409."""
    try:
        db.delete(obj)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="registro em uso")
