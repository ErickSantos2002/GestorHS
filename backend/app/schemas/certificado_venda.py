from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CertificadoVendaCamposOut(BaseModel):
    """Campos ja preenchidos para o modal: cliente e aparelho vem do cadastro."""
    nomecli: str = ""
    cnpj: str = ""
    endcli: str = ""
    modelo: str = ""
    marca: str = ""
    serie: str = ""
    patrimonio: str = ""
    datacompra: Optional[date] = None
    calib_cert: Optional[str] = None
    data_calibracao: Optional[date] = None
    prox_calibragem: Optional[date] = None
    calib_temp: Optional[str] = None
    calib_pressao: Optional[str] = None
    calib_teste1: Optional[str] = None
    calib_teste2: Optional[str] = None
    calib_teste3: Optional[str] = None
    calib_teste_media: Optional[str] = None
    calib_situacao: Optional[str] = None
    ja_gerado: bool = False           # o front usa para dizer "Gerar" ou "Regerar"


class CertificadoVendaIn(BaseModel):
    # cliente/aparelho: opcionais — sobrepoem o cadastro so se vierem preenchidos
    nomecli: Optional[str] = None
    cnpj: Optional[str] = None
    endcli: Optional[str] = None
    serie: Optional[str] = None
    patrimonio: Optional[str] = None
    datacompra: Optional[date] = None
    # calibracao: digitada no modal
    calib_cert: Optional[str] = None
    data_calibracao: Optional[date] = None
    prox_calibragem: Optional[date] = None
    calib_temp: Optional[str] = None
    calib_pressao: Optional[str] = None
    calib_teste1: Optional[str] = None
    calib_teste2: Optional[str] = None
    calib_teste3: Optional[str] = None
    calib_teste_media: Optional[str] = None
    calib_situacao: Optional[str] = None


class CertificadoVendaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    equipamento_cliente: int
    calib_cert: Optional[str] = None
    data_calibracao: Optional[date] = None
    data_geracao: Optional[datetime] = None
    usuario_nome: Optional[str] = None
