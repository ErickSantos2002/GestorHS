"""Cadastro de Empresa com acesso ao banco: unicidade do documento somando
`clientes` e `empresas`, criar e atualizar. Nunca faz commit — quem chama decide,
porque o modal da proposta cria a Empresa na MESMA transacao da proposta.
"""
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.empresa import normalizar_documento
from app.models import Cliente, Empresa
from app.schemas.empresa import EmpresaIn, EmpresaOut

CAMPOS_EMPRESA = ("nome", "cep", "endereco", "numero", "complemento", "bairro",
                  "municipio", "estado", "email", "telefone", "insc_est")

_ROTULO = {"cliente": "Cliente", "empresa": "Empresa"}


class DocumentoDuplicado(Exception):
    def __init__(self, tipo: str, id_: int, nome: Optional[str]):
        self.tipo = tipo
        self.id = id_
        self.nome = nome
        super().__init__(f"Documento já cadastrado como {_ROTULO[tipo]}: {nome or f'#{id_}'}")


class MatrizInexistente(ValueError):
    """`cliente` informado como matriz nao existe."""


def _procurar(db: Session, model, cgc, cpf, ignorar_id):
    filtros = []
    if cgc:
        filtros.append(model.cgc == cgc)
    if cpf:
        filtros.append(model.cpf == cpf)
    if not filtros:
        return None
    query = db.query(model).filter(or_(*filtros))
    if ignorar_id is not None:
        query = query.filter(model.id != ignorar_id)
    return query.first()


def checar_documento_livre(db: Session, cgc: Optional[str], cpf: Optional[str], *,
                           empresa_id: Optional[int] = None, cliente_id: Optional[int] = None,
                           incluir_clientes: bool = True) -> None:
    """Levanta DocumentoDuplicado se o documento ja existe.

    `incluir_clientes=False` e' o uso do cadastro de CLIENTES: la ainda aparece
    duplicata antiga entre clientes (ver operacao-unificar-clientes-duplicados),
    e ela nao pode travar a edicao — so a colisao com Empresa interessa.
    """
    if incluir_clientes:
        achado = _procurar(db, Cliente, cgc, cpf, cliente_id)
        if achado is not None:
            raise DocumentoDuplicado("cliente", achado.id, achado.nome)
    achado = _procurar(db, Empresa, cgc, cpf, empresa_id)
    if achado is not None:
        raise DocumentoDuplicado("empresa", achado.id, achado.nome)


def _conferir_matriz(db: Session, cliente_id: Optional[int]) -> None:
    if cliente_id is not None and db.get(Cliente, cliente_id) is None:
        raise MatrizInexistente("cliente matriz nao encontrado")


def criar_empresa(db: Session, dados: EmpresaIn) -> Empresa:
    cgc, cpf = normalizar_documento(dados.documento)
    checar_documento_livre(db, cgc, cpf)
    _conferir_matriz(db, dados.cliente)
    empresa = Empresa(cgc=cgc, cpf=cpf, cliente=dados.cliente,
                      **{c: getattr(dados, c) for c in CAMPOS_EMPRESA})
    db.add(empresa)
    db.flush()
    return empresa


def atualizar_empresa(db: Session, empresa: Empresa, dados: EmpresaIn) -> Empresa:
    cgc, cpf = normalizar_documento(dados.documento)
    checar_documento_livre(db, cgc, cpf, empresa_id=empresa.id)
    _conferir_matriz(db, dados.cliente)
    empresa.cgc, empresa.cpf, empresa.cliente = cgc, cpf, dados.cliente
    for campo in CAMPOS_EMPRESA:
        setattr(empresa, campo, getattr(dados, campo))
    db.flush()
    return empresa


def saida_empresa(empresa: Empresa) -> EmpresaOut:
    saida = EmpresaOut.model_validate(empresa)
    saida.matriz_nome = empresa.matriz_rel.nome if empresa.matriz_rel is not None else None
    return saida
