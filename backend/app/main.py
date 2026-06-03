from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, funcoes, usuarios, setores, marcas, grupos, categorias, equipamentos, clientes, funcionarios, equipamentos_cliente, fases
from app.core.config import settings

app = FastAPI(title="GestorHS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(funcoes.router)
app.include_router(usuarios.router)
app.include_router(setores.router)
app.include_router(marcas.router)
app.include_router(grupos.router)
app.include_router(categorias.router)
app.include_router(equipamentos.router)
app.include_router(clientes.router)
app.include_router(funcionarios.router)
app.include_router(equipamentos_cliente.router)
app.include_router(fases.router)


@app.get("/health", tags=["infra"])
def health():
    return {"status": "ok"}
