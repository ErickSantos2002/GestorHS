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
def client_exp(client, usuario_comum, fases_seed):
    """Client autenticado como usuário de função Expedição (headers já embutidos)."""
    tok = client.post("/auth/login", json={"email": "comum@hs.com", "senha": "senha123"}).json()
    client.headers["Authorization"] = f"Bearer {tok['access_token']}"
    return client


@pytest.fixture()
def caixa_com_os_cliente_a(db_session):
    """Caixa com uma OS do cliente A já vinculada. Devolve o id da caixa."""
    from app.models import Cliente, Caixa, Ordem
    cli = Cliente(nome="Cliente A")
    cx = Caixa(obs="Caixa cliente A")
    db_session.add_all([cli, cx])
    db_session.flush()
    o = Ordem(cliente=cli.id, fase=4, situacao="E", caixa=cx.id)
    db_session.add(o)
    db_session.commit()
    db_session.refresh(cx)
    return cx.id


@pytest.fixture()
def os_cliente_b(db_session):
    """OS de um cliente B (diferente do cliente A), sem caixa. Devolve o id da OS."""
    from app.models import Cliente, Ordem
    cli = Cliente(nome="Cliente B")
    db_session.add(cli)
    db_session.flush()
    o = Ordem(cliente=cli.id, fase=4, situacao="E")
    db_session.add(o)
    db_session.commit()
    db_session.refresh(o)
    return o.id


@pytest.fixture()
def caixa_recebido(db_session, fases_seed):
    """Caixa em fase 4 (Recebido) com uma OS ativa em fase 4. Devolve o id da caixa."""
    from app.models import Cliente, Caixa, Ordem
    cli = Cliente(nome="Cliente Recebido")
    cx = Caixa(obs="Caixa recebido", fase=4)
    db_session.add_all([cli, cx])
    db_session.flush()
    o = Ordem(cliente=cli.id, fase=4, situacao="E", caixa=cx.id)
    db_session.add(o)
    db_session.commit()
    db_session.refresh(cx)
    return cx.id


@pytest.fixture()
def caixa_lab_um_pendente(db_session, fases_seed):
    """Caixa em fase 5 (Laboratório) com >=2 OS ativas, uma ainda 'pendente'."""
    from app.models import Cliente, Caixa, Ordem
    cli = Cliente(nome="Cliente Lab Pendente")
    cx = Caixa(obs="Caixa lab pendente", fase=5)
    db_session.add_all([cli, cx])
    db_session.flush()
    o1 = Ordem(cliente=cli.id, fase=5, situacao="E", caixa=cx.id, desfecho_lab="concluido")
    o2 = Ordem(cliente=cli.id, fase=5, situacao="E", caixa=cx.id, desfecho_lab="pendente")
    db_session.add_all([o1, o2])
    db_session.commit()
    db_session.refresh(cx)
    return cx.id


@pytest.fixture()
def caixa_lab_todos_terminais(db_session, fases_seed):
    """Caixa em fase 5 (Laboratório) com todas as OS em desfecho terminal."""
    from app.models import Cliente, Caixa, Ordem
    cli = Cliente(nome="Cliente Lab Terminal")
    cx = Caixa(obs="Caixa lab terminal", fase=5)
    db_session.add_all([cli, cx])
    db_session.flush()
    o1 = Ordem(cliente=cli.id, fase=5, situacao="E", caixa=cx.id, desfecho_lab="concluido")
    o2 = Ordem(cliente=cli.id, fase=5, situacao="E", caixa=cx.id, desfecho_lab="sem_conserto")
    db_session.add_all([o1, o2])
    db_session.commit()
    db_session.refresh(cx)
    return cx.id


@pytest.fixture()
def client_fin(client, usuario_financeiro, fases_seed):
    """Client autenticado como usuário de função Financeiro (headers já embutidos)."""
    tok = client.post("/auth/login", json={"email": "fin@hs.com", "senha": "senha123"}).json()
    client.headers["Authorization"] = f"Bearer {tok['access_token']}"
    return client


@pytest.fixture()
def caixa_financeiro(db_session, fases_seed):
    """Caixa em fase 10 (Financeiro) com 2 OS ativas. Devolve o id da caixa."""
    from app.models import Cliente, Caixa, Ordem
    cli = Cliente(nome="Cliente Financeiro")
    cx = Caixa(obs="Caixa financeiro", fase=10)
    db_session.add_all([cli, cx])
    db_session.flush()
    o1 = Ordem(cliente=cli.id, fase=10, situacao="E", caixa=cx.id)
    o2 = Ordem(cliente=cli.id, fase=10, situacao="E", caixa=cx.id)
    db_session.add_all([o1, o2])
    db_session.commit()
    db_session.refresh(cx)
    return cx.id


@pytest.fixture()
def caixa_preparando(db_session, fases_seed):
    """Caixa em fase 7 (Preparando Retorno) com uma OS ativa. Devolve o id da caixa."""
    from app.models import Cliente, Caixa, Ordem
    cli = Cliente(nome="Cliente Preparando")
    cx = Caixa(obs="Caixa preparando", fase=7)
    db_session.add_all([cli, cx])
    db_session.flush()
    o = Ordem(cliente=cli.id, fase=7, situacao="E", caixa=cx.id)
    db_session.add(o)
    db_session.commit()
    db_session.refresh(cx)
    return cx.id


@pytest.fixture()
def client_com(client, usuario_comercial, fases_seed):
    """Client autenticado como usuário de função Comercial Pós-Vendas (headers já embutidos)."""
    tok = client.post("/auth/login", json={"email": "comercial@hs.com", "senha": "senha123"}).json()
    client.headers["Authorization"] = f"Bearer {tok['access_token']}"
    return client


@pytest.fixture()
def caixa_posvendas(db_session, fases_seed):
    """Caixa em fase 6 (Pós-Vendas) com 2 OS ativas, aceite ainda não dado."""
    from app.models import Cliente, Caixa, Ordem
    cli = Cliente(nome="Cliente Pós-Vendas")
    cx = Caixa(obs="Caixa pós-vendas", fase=6)
    db_session.add_all([cli, cx])
    db_session.flush()
    o1 = Ordem(cliente=cli.id, fase=6, situacao="E", caixa=cx.id)
    o2 = Ordem(cliente=cli.id, fase=6, situacao="E", caixa=cx.id)
    db_session.add_all([o1, o2])
    db_session.commit()
    db_session.refresh(cx)
    return cx.id


@pytest.fixture()
def caixa_financeiro_com_nf(db_session, fases_seed):
    """Caixa em fase 10 (Financeiro) com 2 OS ativas, cada uma já com nota_fiscal
    setada diretamente (simula upload prévio) — libera o pagamento sem 409."""
    from app.models import Cliente, Caixa, Ordem
    cli = Cliente(nome="Cliente Financeiro NF")
    cx = Caixa(obs="Caixa financeiro com nf", fase=10)
    db_session.add_all([cli, cx])
    db_session.flush()
    o1 = Ordem(cliente=cli.id, fase=10, situacao="E", caixa=cx.id,
               nota_fiscal="nf.pdf", nota_fiscal_numero="123")
    o2 = Ordem(cliente=cli.id, fase=10, situacao="E", caixa=cx.id,
               nota_fiscal="nf.pdf", nota_fiscal_numero="123")
    db_session.add_all([o1, o2])
    db_session.commit()
    db_session.refresh(cx)
    return cx.id


@pytest.fixture()
def caixa_lab_com_calibracao(db_session, fases_seed):
    """Caixa em fase 5 com uma OS 'concluido' (valores de calibração setados e
    vinculada a um EquipamentoCliente de verdade) e uma OS 'sem_conserto' (também
    vinculada a um EquipamentoCliente, para provar que essa NÃO é espelhada).
    Devolve o id da caixa e os ids dos dois EquipamentoCliente."""
    from datetime import datetime, timezone
    from app.models import Cliente, Equipamento, EquipamentoCliente, Caixa, Ordem
    cli = Cliente(nome="Cliente Lab Calibração")
    eq = Equipamento(descricao="Bafômetro")
    cx = Caixa(obs="Caixa lab calibração", fase=5)
    db_session.add_all([cli, eq, cx])
    db_session.flush()
    ec_ok = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="OK-1")
    ec_sc = EquipamentoCliente(cliente=cli.id, equipamento=eq.id, serie="SC-1")
    db_session.add_all([ec_ok, ec_sc])
    db_session.flush()
    o1 = Ordem(
        cliente=cli.id, fase=5, situacao="E", caixa=cx.id,
        desfecho_lab="concluido", equipamento_cliente=ec_ok.id,
        calib_situacao="Aprovado", calib_cert="C-1", calib_temp="25",
        calib_pressao="1013", calib_teste1="0.10", calib_teste2="0.11",
        calib_teste3="0.12", calib_teste_media="0.11",
        data_calibracao=datetime(2026, 7, 1, tzinfo=timezone.utc),
        prox_calibragem=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )
    o2 = Ordem(
        cliente=cli.id, fase=5, situacao="E", caixa=cx.id,
        desfecho_lab="sem_conserto", desfecho_lab_obs="carcaça trincada",
        equipamento_cliente=ec_sc.id, calib_situacao="Reprovado",
    )
    db_session.add_all([o1, o2])
    db_session.commit()
    db_session.refresh(cx)
    return {"caixa": cx.id, "ec_ok": ec_ok.id, "ec_sc": ec_sc.id}


@pytest.fixture()
def upload_tmp(tmp_path):
    from app.core.config import settings
    anterior = settings.UPLOAD_DIR
    settings.UPLOAD_DIR = str(tmp_path)
    try:
        yield tmp_path
    finally:
        settings.UPLOAD_DIR = anterior
