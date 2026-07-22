import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.database import Base, get_db
from app.models import Funcao, Usuario, UsuarioCliente, Cliente  # registra as tabelas no metadata
from app.core.security import hash_senha


@pytest.fixture(autouse=True)
def _writer_nao_toca_prod(monkeypatch):
    """O writer de logs de integracao abre SessionLocal proprio, que aponta para o
    banco REAL (via .env). Nos testes, redirecionamos esse SessionLocal para um SQLite
    in-memory descartavel: as escritas do writer sucedem em silencio, sem tocar
    producao e sem virar log de erro. Testes que querem verificar o conteudo do log
    injetam db=db_session explicitamente."""
    import app.integrations.log_integracao as li
    from app.models.database import Base

    eng = create_engine("sqlite://", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(bind=eng)
    monkeypatch.setattr(li, "SessionLocal",
                        sessionmaker(autocommit=False, autoflush=False, bind=eng))


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_fk(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

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
    empresa = Cliente(nome="Cliente Teste", cgc="11222333000144")
    db_session.add(empresa)
    db_session.flush()
    c = UsuarioCliente(
        cliente=empresa.id,
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
        senha=hash_senha("senha123"),
        email="comum@hs.com",
        funcao_id=funcao.id,
        precisa_redefinir_senha=False,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


def _get_or_create_funcao(db_session, descricao):
    f = db_session.query(Funcao).filter(Funcao.descricao == descricao).first()
    if f is None:
        f = Funcao(descricao=descricao)
        db_session.add(f)
        db_session.flush()
    return f


@pytest.fixture()
def fases_seed(db_session):
    from app.models import Fase
    exp = _get_or_create_funcao(db_session, "Expedição")
    lab = _get_or_create_funcao(db_session, "Laboratório")
    com = _get_or_create_funcao(db_session, "Comercial Pós-Vendas")
    fin = _get_or_create_funcao(db_session, "Financeiro")
    db_session.add_all([
        Fase(id=4, descricao="Recebido", cor="3b82f6", funcao_responsavel=exp.id),
        Fase(id=5, descricao="Laboratório", cor="6366f1", funcao_responsavel=lab.id),
        Fase(id=6, descricao="Pós-Vendas", cor="f59e0b", funcao_responsavel=com.id),
        Fase(id=10, descricao="Financeiro", cor="a855f7", funcao_responsavel=fin.id),
        Fase(id=7, descricao="Preparando Retorno", cor="14b8a6", funcao_responsavel=exp.id),
        Fase(id=8, descricao="Finalizada", cor="10b981", funcao_responsavel=None),
        Fase(id=9, descricao="Cancelada", cor="ef4444", funcao_responsavel=None),
    ])
    db_session.commit()
    return {"exp": exp.id, "lab": lab.id, "com": com.id, "fin": fin.id}


@pytest.fixture()
def usuario_lab(db_session):
    f = _get_or_create_funcao(db_session, "Laboratório")
    u = Usuario(nome="Lab", senha=hash_senha("senha123"),
                email="lab@hs.com", funcao_id=f.id, precisa_redefinir_senha=False)
    db_session.add(u); db_session.commit(); db_session.refresh(u)
    return u


@pytest.fixture()
def usuario_financeiro(db_session):
    f = _get_or_create_funcao(db_session, "Financeiro")
    u = Usuario(nome="Fin", senha=hash_senha("senha123"),
                email="fin@hs.com", funcao_id=f.id, precisa_redefinir_senha=False)
    db_session.add(u); db_session.commit(); db_session.refresh(u)
    return u


@pytest.fixture()
def usuario_comercial(db_session):
    f = _get_or_create_funcao(db_session, "Comercial Pós-Vendas")
    u = Usuario(nome="Comercial", senha=hash_senha("senha123"),
                email="comercial@hs.com", funcao_id=f.id, precisa_redefinir_senha=False)
    db_session.add(u); db_session.commit(); db_session.refresh(u)
    return u


@pytest.fixture()
def os_base(db_session):
    """Cria um cliente + equipamento + equipamento_cliente e devolve seus ids."""
    from app.models import Cliente, Equipamento, EquipamentoCliente
    cli = Cliente(nome="Cliente OS")
    eq = Equipamento(descricao="Bafômetro")
    db_session.add_all([cli, eq]); db_session.flush()
    ec = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="SER-1", patrimonio="PAT-1")
    db_session.add(ec); db_session.commit(); db_session.refresh(ec)
    return {"cliente": cli.id, "equipamento": eq.id, "equipamento_cliente": ec.id}


@pytest.fixture()
def caixa_base(db_session):
    """Cria uma caixa e devolve seu id (abrir OS exige caixa vinculada)."""
    from app.models import Caixa
    cx = Caixa(obs="Caixa teste")
    db_session.add(cx); db_session.commit(); db_session.refresh(cx)
    return cx.id


@pytest.fixture()
def client_lab(client, usuario_lab, fases_seed):
    """Client autenticado como usuário de função Laboratório (headers já embutidos)."""
    tok = client.post("/auth/login", json={"email": "lab@hs.com", "senha": "senha123"}).json()
    client.headers["Authorization"] = f"Bearer {tok['access_token']}"
    return client


@pytest.fixture()
def os_no_lab(db_session, os_base, caixa_base):
    """OS em fase 5 (Laboratório), vinculada a uma caixa. Devolve o id da OS."""
    from app.models import Ordem
    o = Ordem(
        cliente=os_base["cliente"],
        equipamento_cliente=os_base["equipamento_cliente"],
        fase=5,
        situacao="E",
        caixa=caixa_base,
    )
    db_session.add(o)
    db_session.commit()
    db_session.refresh(o)
    return o.id


@pytest.fixture()
def upload_tmp(tmp_path):
    from app.core.config import settings
    anterior = settings.UPLOAD_DIR
    settings.UPLOAD_DIR = str(tmp_path)
    try:
        yield tmp_path
    finally:
        settings.UPLOAD_DIR = anterior
