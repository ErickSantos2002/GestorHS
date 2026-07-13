from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.models.database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=True)
    senha = Column(Text, nullable=False)            # hash argon2
    email = Column(String(200), nullable=False, unique=True)
    funcao_id = Column(Integer, ForeignKey("funcoes.id"), nullable=True)
    precisa_redefinir_senha = Column(Boolean, nullable=False, default=False)
    ativo = Column(Boolean, nullable=False, default=True)

    funcao_rel = relationship("Funcao", lazy="joined")

    @property
    def funcao(self) -> str | None:
        return self.funcao_rel.descricao if self.funcao_rel else None
