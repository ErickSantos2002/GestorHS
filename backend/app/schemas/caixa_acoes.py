from pydantic import BaseModel


class CaixaAvancarIn(BaseModel):
    obs: str | None = None
    cod_retorno: str | None = None   # obrigatório só em Preparando(7)->Finalizada(8)
    cliente_principal: int | None = None   # usado so no avanco Recebido(4)->Lab(5)


class CaixaCancelarIn(BaseModel):
    motivo: str
