import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.database import Base, get_db
from app.models import Funcao, Usuario, UsuarioCliente  # registra as tabelas no metadata
from app.core.security import hash_senha


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    from app.main import app

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def cliente_portal(db_session):
    c = UsuarioCliente(
        cliente=1,
        nome="Cliente Teste",
        login="cliente1",
        senha=hash_senha("portal123"),
        precisa_redefinir_senha=False,
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture()
def usuario_admin(db_session):
    funcao = Funcao(descricao="Administrador")
    db_session.add(funcao)
    db_session.flush()
    u = Usuario(
        nome="Admin",
        login="admin",
        senha=hash_senha("senha123"),
        email="admin@hs.com",
        funcao_id=funcao.id,
        precisa_redefinir_senha=False,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture()
def usuario_comum(db_session):
    funcao = db_session.query(Funcao).filter(Funcao.descricao == "Expedição").first()
    if funcao is None:
        funcao = Funcao(descricao="Expedição")
        db_session.add(funcao)
        db_session.flush()
    u = Usuario(
        nome="Comum",
        login="comum",
        senha=hash_senha("senha123"),
        email="comum@hs.com",
        funcao_id=funcao.id,
        precisa_redefinir_senha=False,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u
