from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    UPLOAD_DIR: str = "uploads"
    # Onde os scripts gravam o CSV de pendencias. Vazio = `backend/relatorios/`, que
    # serve em desenvolvimento (o compose monta ./backend). Em PRODUCAO a imagem sobe
    # pelo Dockerfile, SEM bind mount: qualquer caminho dentro de /app e efemero e
    # some no redeploy. Aponte para o volume persistente (o mesmo dos uploads).
    RELATORIOS_DIR: str = ""
    # Integracao com o TaskHS (espelhar OS como cards). Vazio = desligada.
    TASKHS_BASE_URL: str = ""   # ex.: "https://taskhs.exemplo/api" (sem barra final)
    TASKHS_API_KEY: str = ""    # header X-API-Key
    # Base publica do backend para o link de download do certificado no card do TaskHS.
    # Vazio = card sai sem link. Sem barra final. Ex.: "https://api.gestorhs..." / "http://localhost:8001"
    CERT_PUBLIC_BASE_URL: str = ""
    # Integracao GrowthHS (CRM). Vazio = desligada (mesmo gating do TaskHS).
    HSGROWTH_BASE_URL: str = ""   # raiz do backend, SEM /api/v1
    HSGROWTH_API_KEY: str = ""    # header X-API-Key
    HSGROWTH_BOARD_SERVICOS: int = 1
    HSGROWTH_BOARD_COBRANCA: int = 2
    # Origens permitidas pelo CORS (front em dev). Sobrescreva via env (JSON ou CSV).
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
    ]
    # Id de catalogo do "Modulo de Calibracao do Bafometro Automatizado PHOEBUS".
    # Fonte unica; tambem usada como default do script de carga (Task 3).
    EQUIPAMENTO_MODULO_ID: int = 47
    # Ids de catalogo dos hospedeiros (nao calibram) e do estoque interno.
    EQUIPAMENTO_PHOEBUS_ID: int = 36
    EQUIPAMENTO_EBS_ID: int = 37
    CLIENTE_ESTOQUE_HS_ID: int = 2

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
