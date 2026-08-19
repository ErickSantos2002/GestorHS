"""Cola entre os endpoints de exportacao e o motor de planilha.

Existe para que os tres endpoints nao repitam o try/except e a montagem do header
de download — que e' onde erram, se repetidos.
"""
from datetime import date, datetime
from typing import Sequence

from fastapi import HTTPException, Response

from app.core import planilha
from app.core.exportacoes import MIME_XLSX, montar_rodape, nome_arquivo
from app.core.planilha import Coluna, PlanilhaGrandeDemais, gerar_xlsx


def carregar_ate_o_teto(query) -> list:
    """Traz no maximo LIMITE_LINHAS + 1 registros.

    O corte e' o que impede uma exportacao sem filtro de hidratar a tabela inteira
    na memoria so' para o gerar_xlsx recusa-la depois. O "+ 1" preserva a fronteira:
    com exatamente o teto a planilha sai, com um a mais o gerar_xlsx levanta.
    """
    return query.limit(planilha.LIMITE_LINHAS + 1).all()


def resposta_xlsx(
    base_nome: str,
    titulo_aba: str,
    colunas: Sequence[Coluna],
    linhas: list[dict],
    filtros: dict,
) -> Response:
    try:
        conteudo = gerar_xlsx(titulo_aba, colunas, linhas, montar_rodape(filtros, datetime.now()))
    except PlanilhaGrandeDemais:
        raise HTTPException(
            status_code=400,
            detail="A exportacao ficou grande demais. Refine o filtro e tente de novo.",
        ) from None
    nome = nome_arquivo(base_nome, date.today())
    return Response(
        content=conteudo,
        media_type=MIME_XLSX,
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )
