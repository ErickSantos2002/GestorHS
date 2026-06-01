from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey
from app.models.database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=True)
    login = Column(String(20), nullable=False, unique=True)
    senha = Column(Text, nullable=False)            # hash argon2
    email = Column(String(200), nullable=True)
    funcao_id = Column(Integer, ForeignKey("funcoes.id"), nullable=True)
    precisa_redefinir_senha = Column(Boolean, nullable=False, default=False)
