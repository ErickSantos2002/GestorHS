"""Camada de serviço de Propostas Técnicas: numeração, totais, itens/aparelhos
e versionamento. Portado de hsgrowth-sistema/backend/app/services/proposal_service.py
(`_to_response`, `_snapshot`, `create`, `update`) e
app/repositories/proposal_repository.py (`next_number`, `_apply_items`,
`create` com retry, `update`, `add_version`).

O GestorHS não usa camada de repository separada: service e repo ficam juntos
aqui, como funções que recebem `db` explicitamente. Tudo de cards/marcador de
serviço/prefill do growthhs foi removido — não existe aqui (sem
`ServiceCard`, sem `card_links`, sem marker).
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import proposta_pdf
from app.core.empresa import dados_destinatario, destinatario_legado
from app.core.empresa_servico import CAMPOS_EMPRESA, criar_empresa
from app.models.proposta import Proposta, PropostaItem, PropostaAparelho
from app.models.proposta_versao import PropostaVersao
from app.models import Cliente, Empresa, EquipamentoCliente
from app.schemas.empresa import EmpresaIn
from app.schemas.proposta import PropostaCreate, PropostaUpdate, PropostaOut, DestinatarioIn

# Campos NOT NULL no modelo: nunca sobrescrever com None num update parcial.
NON_NULLABLE = {"desconto", "frete"}


class DestinatarioInvalido(ValueError):
    """Destinatario inexistente ou aparelhos incompativeis com ele (422)."""


class DestinatarioInativo(Exception):
    """Cliente/Empresa desativado escolhido para proposta nova ou troca (409)."""


# Campos do Cliente que o modal da proposta gerencia. O resto do cadastro
# (obs, whatsapp, inscricoes, contato, grupo...) NUNCA e' tocado por aqui.
_CAMPOS_CLIENTE_TEXTO = ("nome", "cep", "endereco", "complemento", "bairro", "municipio", "estado", "email")


def _numero_do_cliente(valor: Optional[str]) -> Optional[int]:
    """`clientes.numero` e' BigInteger: "S/N" e afins viram nulo no cadastro
    (a copia da proposta guarda o texto que o cadastro aceitou)."""
    texto = (valor or "").strip()
    return int(texto) if texto.isdigit() else None


def _aplicar_destinatario(db: Session, proposta: Proposta, dest: DestinatarioIn) -> None:
    """Grava os dados no cadastro de origem e acerta `cliente`/`empresa` da proposta."""
    if dest.tipo == "cliente":
        cliente = db.get(Cliente, dest.id)
        if cliente is None:
            raise DestinatarioInvalido("cliente nao encontrado")
        trocou = proposta.id is None or proposta.empresa is not None or proposta.cliente != cliente.id
        if trocou and not cliente.ativo:
            raise DestinatarioInativo("cliente desativado")
        for campo in _CAMPOS_CLIENTE_TEXTO:
            setattr(cliente, campo, getattr(dest, campo))
        cliente.numero = _numero_do_cliente(dest.numero)
        cliente.telefones = dest.telefone
        proposta.cliente, proposta.empresa = cliente.id, None
        return

    if dest.tipo == "empresa":
        empresa = db.get(Empresa, dest.id)
        if empresa is None:
            raise DestinatarioInvalido("empresa nao encontrada")
        trocou = proposta.id is None or proposta.empresa != empresa.id
        if trocou and not empresa.ativo:
            raise DestinatarioInativo("empresa desativada")
        for campo in CAMPOS_EMPRESA:
            if campo != "insc_est":          # o modal nao mostra a IE
                setattr(empresa, campo, getattr(dest, campo))
    else:  # nova_empresa
        empresa = criar_empresa(db, EmpresaIn(
            documento=dest.documento, cliente=dest.matriz, nome=dest.nome, cep=dest.cep,
            endereco=dest.endereco, numero=dest.numero, complemento=dest.complemento,
            bairro=dest.bairro, municipio=dest.municipio, estado=dest.estado,
            email=dest.email, telefone=dest.telefone,
        ))
    proposta.empresa, proposta.cliente = empresa.id, empresa.cliente


def _validar_aparelhos(db: Session, cliente_id: Optional[int], ids: list[int]) -> None:
    if not ids:
        return
    if cliente_id is None:
        raise DestinatarioInvalido("proposta sem cliente matriz nao pode ter aparelhos")
    donos = dict(
        db.query(EquipamentoCliente.id, EquipamentoCliente.cliente)
        .filter(EquipamentoCliente.id.in_(ids)).all()
    )
    fora = [i for i in ids if donos.get(i) != cliente_id]
    if fora:
        raise DestinatarioInvalido(f"aparelhos fora da frota do cliente: {fora}")


def _congelar_destinatario(db: Session, proposta: Proposta) -> None:
    """Copia a partir do cadastro JA gravado. Sem cliente nem empresa, mantem o
    que houver (proposta antiga sem vinculo)."""
    db.flush()
    if proposta.empresa is not None:
        empresa = db.get(Empresa, proposta.empresa)
        matriz = db.get(Cliente, empresa.cliente) if empresa.cliente is not None else None
        proposta.destinatario = dados_destinatario(empresa, tipo="empresa", matriz=matriz)
    elif proposta.cliente is not None:
        proposta.destinatario = dados_destinatario(db.get(Cliente, proposta.cliente), tipo="cliente")


def destinatario_atual(proposta: Proposta) -> Optional[dict]:
    """Copia congelada; proposta anterior as Empresas e ainda nao congelada pelo
    script cai no que o PDF sempre mostrou (cadastro + cliente_override). Proposta
    sem cliente nem override (nunca teve destinatario) continua sem um — o legado
    so entra quando ha algo de fato para mostrar."""
    if proposta.destinatario:
        return proposta.destinatario
    if proposta.cliente_rel is None and not proposta.cliente_override:
        return None
    return destinatario_legado(proposta.cliente_rel, proposta.cliente_override)


def proximo_numero(db: Session) -> int:
    """Próximo número sequencial da proposta = max(numero) + 1 (ou 1 se não houver nenhuma)."""
    atual_max = db.query(func.max(Proposta.numero)).scalar()
    return (atual_max or 0) + 1


def _aplicar_itens(proposta: Proposta, itens) -> None:
    """Substitui a lista de itens inteira, calculando o total de cada um."""
    proposta.itens.clear()
    for it in itens:
        total = float(it.quantidade) * float(it.preco_un)
        proposta.itens.append(PropostaItem(
            descricao=it.descricao,
            sku=it.sku,
            quantidade=it.quantidade,
            unidade=it.unidade,
            preco_un=it.preco_un,
            total=total,
        ))


def _aplicar_aparelhos(db: Session, proposta: Proposta, aparelhos) -> None:
    """Substitui a lista de aparelhos inteira, com snapshot puxado da frota
    (equipamento_cliente) no momento da gravação."""
    proposta.aparelhos.clear()
    for a in aparelhos:
        ec = db.get(EquipamentoCliente, a.equipamento_cliente)
        proposta.aparelhos.append(PropostaAparelho(
            equipamento_cliente=a.equipamento_cliente,
            serie=ec.serie if ec else None,
            modelo=ec.equipamento_descricao if ec else None,
            patrimonio=ec.patrimonio if ec else None,
            # prox_calibragem ja e Date (nao DateTime) tanto em EquipamentoCliente
            # quanto em PropostaAparelho: sem .date() aqui (date nao tem esse metodo).
            prox_calibragem=ec.prox_calibragem if ec and ec.prox_calibragem else None,
        ))


def criar_proposta(db: Session, dados: PropostaCreate, vendedor: str, *,
                   vinculo: Optional[tuple[Optional[int], Optional[int]]] = None) -> Proposta:
    """Cria a proposta com número sequencial. Vendedor = quem criou (imutável).

    `dados.destinatario` grava no cadastro e acerta as FKs, tudo na MESMA
    transacao da proposta. `vinculo=(cliente, empresa)` e' o caminho do duplicar:
    repete as FKs da original sem mexer em cadastro.

    Retry anti-corrida: dois requests podem calcular o mesmo `proximo_numero`;
    `numero` e' UNIQUE, entao o segundo commit estoura IntegrityError e tenta de
    novo (até 5x). Cada tentativa refaz tudo, inclusive a Empresa nova, que o
    rollback levou junto.
    """
    payload = dados.model_dump(exclude={"itens", "aparelhos", "vendedor", "destinatario"})
    ultimo_exc: Optional[IntegrityError] = None
    for _ in range(5):
        proposta = Proposta(numero=proximo_numero(db), vendedor=vendedor, **payload)
        if dados.destinatario is not None:
            _aplicar_destinatario(db, proposta, dados.destinatario)
        elif vinculo is not None:
            proposta.cliente, proposta.empresa = vinculo
        _validar_aparelhos(db, proposta.cliente, [a.equipamento_cliente for a in dados.aparelhos or []])
        _aplicar_itens(proposta, dados.itens or [])
        _aplicar_aparelhos(db, proposta, dados.aparelhos or [])
        try:
            # add + flush DENTRO do try: o `numero` repetido estoura ja no flush.
            db.add(proposta)
            _congelar_destinatario(db, proposta)
            db.commit()
            db.refresh(proposta)
            return proposta
        except IntegrityError as exc:
            ultimo_exc = exc
            db.rollback()
    raise ultimo_exc  # esgotou as tentativas


def atualizar_proposta(db: Session, proposta: Proposta, dados: PropostaUpdate,
                        alterado_por: str) -> Proposta:
    """Versiona o estado ANTERIOR (snapshot + PDF arquivado) e aplica as mudanças.

    A versão só é gravada no MESMO commit da alteração: se o destinatário for
    recusado (422/409), nada fica — nem versão órfã. Gerar o PDF da versão
    continua best-effort: falha aí não impede a atualização.
    """
    versao: Optional[PropostaVersao] = None
    try:
        numero_versao = len(proposta.versoes) + 1
        versao = PropostaVersao(
            proposta=proposta.id,
            numero_versao=numero_versao,
            snapshot=snapshot_proposta(proposta),
            pdf_path=proposta_pdf.arquivar_pdf_versao(db, proposta, numero_versao),
            alterado_por=alterado_por,
        )
    except Exception as e:  # noqa: BLE001 - versionamento nunca deve travar o update
        print(f"[PROPOSTA-VERSAO] erro ao arquivar versao da proposta {proposta.id}: {e}")

    # vendedor e imutavel: sempre o do criador, nunca sobrescrito por update.
    payload = dados.model_dump(exclude_unset=True, exclude={"itens", "aparelhos", "vendedor", "destinatario"})
    for k, v in payload.items():
        if v is None and k in NON_NULLABLE:
            continue
        setattr(proposta, k, v)
    if dados.destinatario is not None:
        _aplicar_destinatario(db, proposta, dados.destinatario)
    if dados.aparelhos is not None:
        _validar_aparelhos(db, proposta.cliente, [a.equipamento_cliente for a in dados.aparelhos])
    elif dados.destinatario is not None:
        _validar_aparelhos(db, proposta.cliente,
                           [a.equipamento_cliente for a in proposta.aparelhos if a.equipamento_cliente])
    if dados.itens is not None:
        _aplicar_itens(proposta, dados.itens)
    if dados.aparelhos is not None:
        _aplicar_aparelhos(db, proposta, dados.aparelhos)
    if versao is not None:
        db.add(versao)
    _congelar_destinatario(db, proposta)
    db.commit()
    db.refresh(proposta)
    return proposta


def montar_saida(db: Session, proposta: Proposta) -> PropostaOut:
    """Monta o `PropostaOut` calculando os totais e resolvendo o destinatario
    (copia congelada, com fallback ao legado para proposta antiga)."""
    total_itens = sum(float(i.total) for i in proposta.itens)
    total = total_itens + float(proposta.frete or 0) - float(proposta.desconto or 0)

    saida = PropostaOut.model_validate(proposta)
    saida.total_itens = round(total_itens, 2)
    saida.total = round(total, 2)

    dest = destinatario_atual(proposta)
    saida.destinatario = dest
    saida.cliente_nome = (dest or {}).get("nome")
    saida.cliente_documento = (dest or {}).get("documento")
    return saida


def snapshot_proposta(proposta: Proposta) -> dict:
    """Snapshot exibível do estado atual da proposta (para o histórico de versões)."""
    total_itens = sum(float(i.total) for i in proposta.itens)
    total = total_itens + float(proposta.frete or 0) - float(proposta.desconto or 0)
    dest = destinatario_atual(proposta)
    return {
        "numero": proposta.numero,
        "data": proposta.data.isoformat() if proposta.data else None,
        "cliente_nome": (dest or {}).get("nome"),
        "cliente_documento": (dest or {}).get("documento"),
        "empresa": proposta.empresa,
        "destinatario": dest,
        "total": round(total, 2),
        "total_itens": round(total_itens, 2),
        "desconto": float(proposta.desconto or 0),
        "frete": float(proposta.frete or 0),
        "itens": [
            {
                "descricao": i.descricao,
                "sku": i.sku,
                "quantidade": float(i.quantidade),
                "unidade": i.unidade,
                "preco_un": float(i.preco_un),
                "total": float(i.total),
            }
            for i in proposta.itens
        ],
    }
