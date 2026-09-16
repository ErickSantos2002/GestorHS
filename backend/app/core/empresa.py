"""Regras puras de Empresa (filial) e do destinatario da proposta. Sem I/O.

O destinatario da proposta e' um Cliente (matriz, dono da frota) ou uma Empresa
(filial, sem frota, com matriz opcional). A proposta guarda uma COPIA CONGELADA
dos dados do destinatario no momento em que foi salva (`propostas.destinatario`),
para o PDF antigo nao mudar quando o cadastro mudar. `dados_destinatario` e' a
unica funcao que conhece o formato desse JSON.
"""
import re
from typing import Literal, Optional


class DocumentoInvalido(ValueError):
    """CNPJ/CPF com tamanho ou digito verificador errado."""


def so_digitos(v) -> str:
    return re.sub(r"\D", "", str(v or ""))


def _dv(base: str, pesos: list[int]) -> str:
    resto = sum(int(x) * p for x, p in zip(base, pesos)) % 11
    return "0" if resto < 2 else str(11 - resto)


def cnpj_valido(d: str) -> bool:
    if len(d) != 14 or not d.isdigit() or d == d[0] * 14:
        return False
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    d1 = _dv(d[:12], p1)
    d2 = _dv(d[:12] + d1, [6] + p1)
    return d[12:] == d1 + d2


def cpf_valido(d: str) -> bool:
    if len(d) != 11 or not d.isdigit() or d == d[0] * 11:
        return False
    for n in (9, 10):
        soma = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if (soma * 10) % 11 % 10 != int(d[n]):
            return False
    return True


def normalizar_documento(texto) -> tuple[Optional[str], Optional[str]]:
    """Devolve (cgc, cpf) so com digitos — exatamente um dos dois preenchido."""
    d = so_digitos(texto)
    if len(d) == 14:
        if not cnpj_valido(d):
            raise DocumentoInvalido("CNPJ invalido")
        return d, None
    if len(d) == 11:
        if not cpf_valido(d):
            raise DocumentoInvalido("CPF invalido")
        return None, d
    raise DocumentoInvalido("Documento deve ser CNPJ (14 digitos) ou CPF (11 digitos)")


def _texto(v) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def dados_destinatario(registro, *, tipo: Literal["cliente", "empresa"], matriz=None) -> dict:
    """Copia congelada a partir do cadastro ja salvo.

    Cliente: telefone vem de `telefones` (onde a proposta grava), com celular e
    whatsapp de reserva; `numero` e' inteiro no cadastro e vira texto aqui.
    """
    if tipo == "cliente":
        telefone = registro.telefones or registro.celular or registro.whatsapp
    else:
        telefone = registro.telefone
    dados = {
        "tipo": tipo,
        "id": registro.id,
        "nome": _texto(registro.nome),
        "documento": registro.cgc or registro.cpf,
        "cep": _texto(registro.cep),
        "endereco": _texto(registro.endereco),
        "numero": _texto(registro.numero),
        "complemento": _texto(registro.complemento),
        "bairro": _texto(registro.bairro),
        "municipio": _texto(registro.municipio),
        "estado": _texto(registro.estado),
        "email": _texto(registro.email),
        "telefone": _texto(telefone),
    }
    if tipo == "empresa":
        dados["matriz_id"] = matriz.id if matriz is not None else None
        dados["matriz_nome"] = matriz.nome if matriz is not None else None
    return dados


def destinatario_legado(cliente, override: Optional[dict]) -> dict:
    """O que o PDF mostrava ANTES das Empresas: cadastro do cliente com o
    `cliente_override` por cima, campo a campo.

    Reproduz as escolhas do PDF antigo de proposito — nao imprimia numero nem
    bairro do cadastro, e lia celular antes de telefones — para uma proposta
    antiga sair igual depois da mudanca.
    """
    ov = override or {}

    def campo(chave: str, do_cadastro):
        return _texto(ov.get(chave)) or _texto(do_cadastro)

    c = cliente
    return {
        "tipo": "cliente",
        "id": c.id if c is not None else None,
        "nome": campo("nome", c.nome if c else None),
        "documento": so_digitos(ov.get("documento")) or ((c.cgc or c.cpf) if c else None) or None,
        "cep": so_digitos(ov.get("cep")) or (_texto(c.cep) if c else None) or None,
        "endereco": campo("endereco", c.endereco if c else None),
        "numero": None,
        "complemento": None,
        "bairro": None,
        "municipio": campo("municipio", c.municipio if c else None),
        "estado": campo("estado", c.estado if c else None),
        "email": campo("email", c.email if c else None),
        "telefone": campo("telefone", (c.celular or c.whatsapp or c.telefones) if c else None),
    }


def linha_endereco(dest: dict) -> str:
    """`Endereco, numero complemento - bairro`, pulando o que estiver vazio."""
    linha = _texto(dest.get("endereco")) or ""
    numero = _texto(dest.get("numero"))
    complemento = _texto(dest.get("complemento"))
    bairro = _texto(dest.get("bairro"))
    if numero:
        linha = f"{linha}, {numero}" if linha else numero
    if complemento:
        linha = f"{linha} {complemento}".strip()
    if bairro:
        linha = f"{linha} - {bairro}" if linha else bairro
    return linha
