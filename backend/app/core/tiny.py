"""Regras puras da integracao com o Tiny ERP (API v2). Sem I/O.

O que a API do Tiny faz de diferente, verificado na conta da empresa em
16/09/2026 (ver a spec):

- HTTP e' sempre 200; o que vale e' `retorno.status` / `retorno.codigo_erro`.
- "nao encontrado" e' o ERRO 20, nao uma lista vazia.
- Sem `tipos_contato`, o contato nasce como "Outro" — os contatos da empresa
  sao "Cliente". E o campo ACUMULA a cada alteracao.
- `contato.alterar.php` APAGA o que nao for enviado: por isso a edicao le o
  contato antes e devolve inteiro o que e' do Tiny (codigo, tipos, fantasia,
  pessoas de contato, e-mail de NFe...).
- O Tiny casa o municipio pela tabela dele: aceitou "Araucaria" sem acento e
  preencheu a UF sozinho. Nao normalizamos nada aqui.
"""
from dataclasses import dataclass
from typing import Optional

NAO_ENCONTRADO = 20
DUPLICIDADE = 30
VALIDACAO = 31
TOKEN_INVALIDO = 2
LIMITE = (6, 11)

# Limite de caracteres do Tiny para o nome do contato.
_MAX_NOME = 50


@dataclass
class Resultado:
    """Leitura do `retorno` do Tiny, seja de pesquisa, inclusao ou alteracao."""
    ok: bool
    id: Optional[int] = None
    codigo_erro: Optional[int] = None
    mensagem: str = ""

    @property
    def nao_encontrado(self) -> bool:
        return self.codigo_erro == NAO_ENCONTRADO

    @property
    def duplicidade(self) -> bool:
        return self.codigo_erro == DUPLICIDADE

    @property
    def deve_tentar_de_novo(self) -> bool:
        """Bloqueio por excesso de chamadas: passa sozinho, nao e' erro de dado."""
        return self.codigo_erro in LIMITE


def _texto(v) -> str:
    return str(v or "").strip()


def montar_contato(empresa) -> dict:
    """Campos que o GestorHS e' dono. Campo vazio fica de fora do payload."""
    cgc, cpf = _texto(empresa.cgc), _texto(empresa.cpf)
    contato = {
        "nome": _texto(empresa.nome)[:_MAX_NOME],
        "cpf_cnpj": cgc or cpf,
        "tipo_pessoa": "J" if cgc else "F",
        "ie": _texto(empresa.insc_est),
        "endereco": _texto(empresa.endereco),
        "numero": _texto(empresa.numero),
        "complemento": _texto(empresa.complemento),
        "bairro": _texto(empresa.bairro),
        "cidade": _texto(empresa.municipio),
        "uf": _texto(empresa.estado),
        "cep": _texto(empresa.cep),
        "email": _texto(empresa.email),
        "fone": _texto(empresa.telefone),
    }
    return {k: v for k, v in contato.items() if v != ""}


def contato_para_criar(empresa) -> dict:
    """`tipos_contato` SO aqui: na alteracao ele acumularia."""
    return {
        "sequencia": 1,
        "situacao": "A",
        **montar_contato(empresa),
        "tipos_contato": [{"tipo": "Cliente"}],
    }


def contato_para_alterar(empresa, atual: dict) -> dict:
    """Contato INTEIRO: o que veio do Tiny por baixo, os nossos campos por cima."""
    contato = dict(atual)
    contato.update(montar_contato(empresa))
    contato["sequencia"] = 1
    contato["situacao"] = "A"
    return contato


def _mensagem(erros) -> str:
    if isinstance(erros, list):
        return "; ".join(_texto(e.get("erro") if isinstance(e, dict) else e) for e in erros).strip("; ")
    return _texto(erros)


def ler_resposta(corpo: dict) -> Resultado:
    retorno = (corpo or {}).get("retorno")
    if not isinstance(retorno, dict):
        return Resultado(ok=False, mensagem="resposta do Tiny fora do formato esperado")

    if _texto(retorno.get("status")) != "OK":
        try:
            codigo = int(retorno.get("codigo_erro"))
        except (TypeError, ValueError):
            codigo = None
        return Resultado(ok=False, codigo_erro=codigo,
                         mensagem=_mensagem(retorno.get("erros")) or "erro sem descricao")

    registros = retorno.get("registros") or []
    if registros:
        registro = registros[0].get("registro", {})
        if _texto(registro.get("status")) != "OK":
            return Resultado(ok=False, mensagem=_mensagem(registro.get("erros")) or "registro recusado")
        try:
            return Resultado(ok=True, id=int(registro.get("id")))
        except (TypeError, ValueError):
            return Resultado(ok=False, mensagem="registro sem id")

    contatos = retorno.get("contatos") or []
    if contatos:
        try:
            return Resultado(ok=True, id=int(contatos[0].get("contato", {}).get("id")))
        except (TypeError, ValueError):
            return Resultado(ok=False, mensagem="contato sem id")

    contato = retorno.get("contato")
    if isinstance(contato, dict):
        try:
            return Resultado(ok=True, id=int(contato.get("id")))
        except (TypeError, ValueError):
            return Resultado(ok=False, mensagem="contato sem id")

    return Resultado(ok=False, mensagem="resposta OK sem registros nem contatos")
