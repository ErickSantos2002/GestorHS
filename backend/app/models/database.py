from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# pool_recycle + keepalives evitam o "login pendura" depois da maquina ficar ociosa:
# o socket TCP do Postgres remoto morre meio-aberto e o pre_ping tambem travaria nele.
# Reciclar por idade (nao reusar a conexao que dormiu) e keepalives resolvem sem reiniciar.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={
        "connect_timeout": 10,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
    },
)

Base = declarative_base()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
