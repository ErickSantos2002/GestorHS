"""Regra unica de "este termo de busca vale como documento?".

Todas as buscas de Cliente/Empresa oferecem, no mesmo campo, nome, municipio,
serie e documento. Extrair os digitos de QUALQUER termo fazia a serie virar
busca de CNPJ: `WAO4O0065` virava `40065` e trazia tres clientes sem relacao
(16/09/2026). Documento so' se escreve com digitos e pontuacao — uma letra no
termo significa que ele e' nome, municipio ou serie.
"""

import re


def digitos_de_documento(q: str | None) -> str | None:
    """Os digitos de `q` quando ele PARECE documento, senao None.

    Devolver None e' o sinal para o chamador nao incluir cgc/cpf nos filtros.
    """
    if not q or any(c.isalpha() for c in q):
        return None
    return re.sub(r"\D", "", q) or None
