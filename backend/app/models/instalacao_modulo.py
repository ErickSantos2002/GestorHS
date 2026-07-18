from sqlalchemy import Column, Integer, String, Date, ForeignKey, Index, text

from app.models.database import Base


class InstalacaoModulo(Base):
    """Qual modulo de calibracao esta instalado em qual Phoebus, ao longo do tempo.

    `saiu_em` nulo = instalacao ABERTA = elo atual. Os dois lados apontam para
    `equipamentos_cliente` (Phoebus e Modulo sao ambos linhas dessa tabela).
    ATENCAO: nada a ver com a coluna legada `equipamentos_cliente.modulo` (inteiro).
    """
    __tablename__ = "instalacoes_modulo"

    id = Column(Integer, primary_key=True, index=True)
    modulo = Column(Integer, ForeignKey("equipamentos_cliente.id"), nullable=False)
    phoebus = Column(Integer, ForeignKey("equipamentos_cliente.id"), nullable=False)
    entrou_em = Column(Date, nullable=True)
    saiu_em = Column(Date, nullable=True)
    origem = Column(String(100), nullable=True)

    __table_args__ = (
        Index("uq_instalacao_modulo_aberta", "modulo", unique=True,
              postgresql_where=text("saiu_em IS NULL"), sqlite_where=text("saiu_em IS NULL")),
        Index("uq_instalacao_phoebus_aberta", "phoebus", unique=True,
              postgresql_where=text("saiu_em IS NULL"), sqlite_where=text("saiu_em IS NULL")),
    )
