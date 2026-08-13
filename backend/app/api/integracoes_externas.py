"""Consultas a APIs publicas (CEP/CNPJ) usadas para preencher dados na proposta.

So para usuario interno — nao e' exposto ao portal do cliente. O valor do path
e' validado como digitos antes de compor a URL do provedor.
"""
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_usuario
from app.core import enderecos
from app.integrations import enderecos_client
from app.models import Usuario

router = APIRouter(prefix="/integracoes", tags=["integracoes"])


def _executar(fn, valor: str) -> dict:
    try:
        return fn(valor)
    except enderecos.DocumentoInvalido as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except enderecos.NaoEncontrado as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    # Antes de ProvedorIndisponivel: LimiteExcedido herda dele. Cota estourada
    # nao e' o servico fora do ar — passa em segundos, e o usuario precisa saber
    # que vale tentar de novo em vez de achar que a busca quebrou.
    except enderecos.LimiteExcedido as e:
        raise HTTPException(status_code=429, detail="muitas consultas seguidas") from e
    except enderecos.ProvedorIndisponivel as e:
        raise HTTPException(status_code=502, detail="servico de consulta indisponivel") from e


@router.get("/cep/{cep}")
def consultar_cep(cep: str, _: Usuario = Depends(get_current_usuario)):
    return _executar(enderecos_client.buscar_cep, cep)


@router.get("/cnpj/{cnpj}")
def consultar_cnpj(cnpj: str, _: Usuario = Depends(get_current_usuario)):
    return _executar(enderecos_client.buscar_cnpj, cnpj)
