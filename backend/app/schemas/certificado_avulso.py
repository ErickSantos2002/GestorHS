from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CertificadoAvulsoIn(BaseModel):
    equipamento: int          # o aparelho do TEMPLATE escolhido
    tipo: str                 # C / M
    # dados digitados (todos opcionais — o laboratorio preenche o que tiver)
    nomecli: Optional[str] = None
    cnpj: Optional[str] = None
    endcli: Optional[str] = None
    modelo: Optional[str] = None
    marca: Optional[str] = None
    serie: Optional[str] = None
    patrimonio: Optional[str] = None
    datacompra: Optional[date] = None
    os: Optional[str] = None                    # default do form: "XXXX"
    data_recebimento: Optional[date] = None     # default do form: hoje
    calib_cert: Optional[str] = None
    data_calibracao: Optional[date] = None
    calib_temp: Optional[str] = None
    calib_pressao: Optional[str] = None
    calib_teste1: Optional[str] = None
    calib_teste2: Optional[str] = None
    calib_teste3: Optional[str] = None
    calib_teste_media: Optional[str] = None
    calib_situacao: Optional[str] = None


class CertificadoAvulsoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tipo: str
    nomecli: Optional[str] = None
    serie: Optional[str] = None
    calib_cert: Optional[str] = None
    data_calibracao: Optional[date] = None
    data_geracao: Optional[datetime] = None
    usuario_nome: Optional[str] = None
