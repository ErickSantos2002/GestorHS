import contextlib
import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, funcoes, usuarios, setores, marcas, grupos, categorias, equipamentos, clientes, funcionarios, equipamentos_cliente, fases, ordens, tipos_calibragem, alertas, portal, solicitacoes, usuarios_cliente, dashboard, fotos, certificados, caixas, certificados_modelo, certificados_os, publico, notas_fiscais, certificados_avulsos, certificados_gerais, certificados_venda, logs_integracao, servicos, produtos, propostas, integracao_growthhs, integracoes_externas, certificados_config, certificados_emitidos, manutencao_servicos, manutencoes
from app.core.config import settings
from app.tarefas import vencendo


def _configurar_log() -> None:
    """Faz os logs de `app.*` chegarem ao stdout em nivel INFO.

    Sem isso o root logger fica em WARNING e o uvicorn so mostra os proprios logs:
    todo `logger.info`/`logger.error` nosso e' descartado em silencio — inclusive o
    relatorio de falhas do worker diario, que em producao (Dockerfile, sem bind
    mount) e' a diagnose que sobrevive. Mexemos so no namespace `app` de proposito,
    para nao ligar o INFO de bibliotecas de terceiros junto.
    """
    log = logging.getLogger("app")
    log.setLevel(logging.INFO)
    if not log.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        log.addHandler(h)


_configurar_log()


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI):
    """Sobe o worker diario do GrowthHS junto com a API.

    Nasce desligado (`JOB_VENCENDO_ATIVO=false`) — em desenvolvimento a env aponta
    para o banco de producao com a chave real. No shutdown a task e' cancelada; o
    `suppress` engole o CancelledError esperado.
    """
    tarefa = vencendo.iniciar()
    try:
        yield
    finally:
        if tarefa is not None:
            tarefa.cancel()
            with contextlib.suppress(BaseException):
                await tarefa


app = FastAPI(title="GestorHS API", lifespan=lifespan)

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
# Antes do router de frota: os dois usam o prefixo /equipamentos-cliente, e as rotas
# especificas do certificado de venda precisam casar antes das genericas da frota.
app.include_router(certificados_venda.router)
app.include_router(equipamentos_cliente.router)
app.include_router(fases.router)
app.include_router(ordens.router)
app.include_router(tipos_calibragem.router)
app.include_router(alertas.router)
app.include_router(portal.router)
app.include_router(solicitacoes.router)
app.include_router(usuarios_cliente.router)
app.include_router(dashboard.router)
app.include_router(fotos.router)
app.include_router(certificados.router)
app.include_router(caixas.router)
app.include_router(certificados_modelo.router)
app.include_router(certificados_os.router)
app.include_router(publico.router)
app.include_router(notas_fiscais.router)
app.include_router(certificados_avulsos.router)
app.include_router(certificados_gerais.router)
app.include_router(certificados_config.router)
app.include_router(certificados_emitidos.router)
app.include_router(logs_integracao.router)
app.include_router(servicos.router)
app.include_router(produtos.router)
app.include_router(propostas.router)
app.include_router(integracao_growthhs.router)
app.include_router(integracoes_externas.router)
app.include_router(manutencao_servicos.router)
app.include_router(manutencoes.router)


@app.get("/health", tags=["infra"])
def health():
    return {"status": "ok"}
