from sqlalchemy import Column, Integer, BigInteger, String, Text, Boolean, UniqueConstraint
from app.models.database import Base


class UsuarioCliente(Base):
    __tablename__ = "usuarios_cliente"
    __table_args__ = (UniqueConstraint("cliente", "login", name="uq_usuarios_cliente_login"),)

    id = Column(Integer, primary_key=True, index=True)
    # FK para clientes.id será adicionada quando o modelo Cliente for implementado
    cliente = Column(BigInteger, nullable=False)
    nome = Column(String(100), nullable=True)
    login = Column(String(20), nullable=False)
    senha = Column(Text, nullable=False)            # hash argon2
    email = Column(String(200), nullable=True)
    precisa_redefinir_senha = Column(Boolean, nullable=False, default=False)
