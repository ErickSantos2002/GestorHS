import os

# Garante que os imports de app.core.config funcionem nos testes sem depender de um .env real.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://u:p@localhost:5432/db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
