from pydantic import BaseModel, Field
from typing import Optional


class SetorOut(BaseModel):
    id: int
    descricao: str
    model_config = {"from_attributes": True}


class SetorCreate(BaseModel):
    descricao: str = Field(min_length=1)


class SetorUpdate(BaseModel):
    descricao: Optional[str] = Field(default=None, min_length=1)
