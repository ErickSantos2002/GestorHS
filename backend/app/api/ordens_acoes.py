from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Ordem, Fase, LogOS, Usuario
from app.core import os_workflow as wf

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


def espelhar_calibracao_valores(db: Session, ec, valores: dict,
                                ult=None, prox=None) -> None:
    """Copia resultados de calibracao para o equipamento_cliente a partir de valores soltos.

    Miolo compartilhado entre o fluxo da OS (`espelhar_calibracao`) e o certificado de
    venda, que nao tem OS. Valor ausente/None NAO apaga o que ja existe no cadastro.
    """
    for campo in _CAMPOS_CALIB:
        valor = valores.get(campo)
        if valor is not None:
            setattr(ec, campo, valor)
    if ult is not None:
        ec.ult_calibragem = ult
    if prox is not None:
        ec.prox_calibragem = prox


def espelhar_calibracao(db: Session, ordem) -> None:
    """Copia os resultados de calibração da OS para o equipamento_cliente."""
    from app.models import EquipamentoCliente
    if not ordem.equipamento_cliente:
        return
    ec = db.query(EquipamentoCliente).filter(EquipamentoCliente.id == ordem.equipamento_cliente).first()
    if ec is None:
        return
    espelhar_calibracao_valores(
        db, ec,
        {campo: getattr(ordem, campo) for campo in _CAMPOS_CALIB},
        ult=ordem.data_calibracao.date() if ordem.data_calibracao is not None else None,
        prox=ordem.prox_calibragem.date() if ordem.prox_calibragem is not None else None,
    )


def concluir_laboratorio(db: Session, ordem) -> None:
    """Conclui o laboratório de uma OS: espelha os resultados na frota e marca o
    desfecho. NÃO registra log — cada chamador loga com o próprio texto.
    Idempotente na prática: `espelhar_calibracao` só sobrescreve campos do
    equipamento_cliente, sem inserir histórico."""
    espelhar_calibracao(db, ordem)
    ordem.desfecho_lab = wf.DESFECHO_CONCLUIDO
    ordem.desfecho_lab_obs = None
