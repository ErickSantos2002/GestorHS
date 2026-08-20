from pydantic import BaseModel


class CaixaAvancarIn(BaseModel):
    obs: str | None = None
    cod_retorno: str | None = None   # obrigatório só em Preparando(7)->Finalizada(8)
    cliente_principal: int | None = None   # usado so no avanco Recebido(4)->Lab(5)
    # Dispensa a nota fiscal no avanco Financeiro(10)->Preparando(7). So o
    # Administrador pode pedir — existe para as caixas do modelo antigo, que
    # nao tem nota para anexar. O endpoint recusa para qualquer outra funcao.
    sem_nota_fiscal: bool = False


class CaixaCancelarIn(BaseModel):
    motivo: str
