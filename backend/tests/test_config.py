def test_settings_carrega_do_ambiente(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://u:p@localhost:5432/db")
    monkeypatch.setenv("JWT_SECRET_KEY", "segredo-de-teste")
    from app.core.config import Settings
    s = Settings()
    assert s.DATABASE_URL.endswith("/db")
    assert s.JWT_SECRET_KEY == "segredo-de-teste"
    assert s.JWT_ALGORITHM == "HS256"
    assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 30
