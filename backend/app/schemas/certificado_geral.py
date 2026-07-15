from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CertificadoGeralOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str
    data_upload: Optional[datetime] = None
    usuario_nome: Optional[str] = None
    link: Optional[str] = None
