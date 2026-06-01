from fastapi import FastAPI
from app.api import auth

app = FastAPI(title="GestorHS API")

app.include_router(auth.router)


@app.get("/health", tags=["infra"])
def health():
    return {"status": "ok"}
