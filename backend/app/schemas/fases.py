from pydantic import BaseModel, ConfigDict, Field


class FaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    descricao: str
    cor: str
    funcao_responsavel: int | None = None
    funcao_nome: str | None = None


class FaseUpdate(BaseModel):
    funcao_responsavel: int | None = None


class FuncaoCreate(BaseModel):
    descricao: str = Field(min_length=1)


class FuncaoUpdate(BaseModel):
    descricao: str = Field(min_length=1)
