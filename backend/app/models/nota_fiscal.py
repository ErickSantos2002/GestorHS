from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.models.database import Base


class NotaFiscal(Base):
    """Uma nota fiscal da CAIXA. A caixa pode levar mais de uma — alem da nota do
    servico vai, as vezes, a nota de remessa do envio.

    `ordem` e' preenchido SO pelo backfill da migracao 0029: marca que os
    arquivos daquela nota ficaram no subdir antigo, o da OS. Nota criada pela
    tela nasce com `ordem` nulo e vive no subdir da caixa.

    O par PDF+XML e' obrigatorio (as duas colunas NOT NULL): nota pela metade foi
    justamente o problema que fez o campo unico virar dois, na migracao 0026.
    """
    __tablename__ = "notas_fiscais"

    id = Column(Integer, primary_key=True, index=True)
    caixa = Column(Integer, ForeignKey("caixas.id"), nullable=False, index=True)
    numero = Column(String(50), nullable=False)
    arquivo_pdf = Column(String(50), nullable=False)   # basename em disco
    arquivo_xml = Column(String(50), nullable=False)   # basename em disco
    ordem = Column(Integer, ForeignKey("ordens.id"), nullable=True)
    criado_em = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    criado_por = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
