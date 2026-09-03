from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


class LogIntegracaoOut(BaseModel):
    id: int
    criado_em: Optional[datetime] = None
    integracao: str
    tipo: str
    external_id: Optional[str] = None
    referencia_os: Optional[int] = None
    # Para onde o numero da referencia aponta. O card e' da caixa desde set/2026, mas
    # os pulos por modulo continuam guardando o id da OS — a tela precisa saber qual
    # dos dois esta olhando para montar o link certo. None quando nao ha referencia.
    referencia_tipo: Optional[Literal["os", "caixa"]] = None
    status: str
    motivo: Optional[str] = None
    http_status: Optional[int] = None
    resposta: Optional[str] = None
    payload: Optional[dict] = None
    model_config = {"from_attributes": True}


class EstadoIntegracoes(BaseModel):
    taskhs_ativo: bool
    growthhs_ativo: bool


class LogsPage(BaseModel):
    items: list[LogIntegracaoOut]
    total: int
    estado: EstadoIntegracoes


class ReenvioOut(BaseModel):
    ok: bool
    mensagem: Optional[str] = None
