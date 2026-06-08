from sqlalchemy import Column, Integer, String, DateTime
from app.models.database import Base


class CertificadoImagem(Base):
    __tablename__ = "certificado_imagens"

    id = Column(Integer, primary_key=True, index=True)
    arquivo = Column(String(120), nullable=False)
    nome = Column(String(150), nullable=True)
    datacad = Column(DateTime(timezone=True), nullable=True)

    @property
    def url(self):
        return f"/certificado-imagens/arquivo/{self.arquivo}"
