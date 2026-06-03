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


_CAMPOS_CALIB = (
    "calib_cert", "calib_temp", "calib_pressao", "calib_teste1", "calib_teste2",
    "calib_teste3", "calib_teste_media", "calib_situacao",
)


def espelhar_calibracao(db: Session, ordem) -> None:
    """Copia os resultados de calibração da OS para o equipamento_cliente."""
    from app.models import EquipamentoCliente
    if not ordem.equipamento_cliente:
        return
    ec = db.query(EquipamentoCliente).filter(EquipamentoCliente.id == ordem.equipamento_cliente).first()
    if ec is None:
        return
    for campo in _CAMPOS_CALIB:
        valor = getattr(ordem, campo)
        if valor is not None:
            setattr(ec, campo, valor)
    if ordem.data_calibracao is not None:
        ec.ult_calibragem = ordem.data_calibracao.date()
    if ordem.prox_calibragem is not None:
        ec.prox_calibragem = ordem.prox_calibragem.date()
