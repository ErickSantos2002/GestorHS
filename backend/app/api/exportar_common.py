"""Cola entre os endpoints de exportacao e o motor de planilha.

Existe para que os quatro endpoints nao repitam o try/except e a montagem do header
de download — que e' onde erram, se repetidos.
"""
from datetime import date, datetime
from typing import Sequence

from fastapi import HTTPException, Response

from app.core.exportacoes import MIME_XLSX, montar_rodape, nome_arquivo
from app.core.planilha import Coluna, PlanilhaGrandeDemais, gerar_xlsx


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
        )
    nome = nome_arquivo(base_nome, date.today())
    return Response(
        content=conteudo,
        media_type=MIME_XLSX,
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )
