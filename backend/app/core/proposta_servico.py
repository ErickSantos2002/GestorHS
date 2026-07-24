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
from app.models.proposta import Proposta, PropostaItem, PropostaAparelho
from app.models.proposta_versao import PropostaVersao
from app.schemas.proposta import PropostaCreate, PropostaUpdate, PropostaOut

# Campos NOT NULL no modelo: nunca sobrescrever com None num update parcial.
NON_NULLABLE = {"desconto", "frete"}


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
    from app.models import EquipamentoCliente

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


def criar_proposta(db: Session, dados: PropostaCreate, vendedor: str) -> Proposta:
    """Cria a proposta com número sequencial. Vendedor = quem criou (imutável
    depois — ver `atualizar_proposta`, que nunca sobrescreve esse campo).

    Retry anti-corrida: dois requests concorrentes podem calcular o mesmo
    `proximo_numero` antes de qualquer um commitar; a coluna `numero` é
    UNIQUE, então o segundo commit estoura IntegrityError — tenta de novo
    recalculando o número (até 5x) em vez de propagar erro de corrida.
    """
    payload = dados.model_dump(exclude={"itens", "aparelhos", "vendedor"})
    ultimo_exc: Optional[IntegrityError] = None
    for _ in range(5):
        proposta = Proposta(numero=proximo_numero(db), vendedor=vendedor, **payload)
        _aplicar_itens(proposta, dados.itens or [])
        _aplicar_aparelhos(db, proposta, dados.aparelhos or [])
        db.add(proposta)
        try:
            db.commit()
            db.refresh(proposta)
            return proposta
        except IntegrityError as exc:
            ultimo_exc = exc
            db.rollback()
    raise ultimo_exc  # esgotou as tentativas


def atualizar_proposta(db: Session, proposta: Proposta, dados: PropostaUpdate,
                        alterado_por: str) -> Proposta:
    """Versiona o estado ANTERIOR (snapshot + PDF arquivado) antes de aplicar
    as mudanças — best-effort: falha ao gerar/arquivar a versão não deve
    impedir a atualização da proposta em si.
    """
    try:
        numero_versao = len(proposta.versoes) + 1
        snapshot = snapshot_proposta(proposta)
        pdf_path = proposta_pdf.arquivar_pdf_versao(db, proposta, numero_versao)
        db.add(PropostaVersao(
            proposta=proposta.id,
            numero_versao=numero_versao,
            snapshot=snapshot,
            pdf_path=pdf_path,
            alterado_por=alterado_por,
        ))
        db.commit()
    except Exception as e:  # noqa: BLE001 - versionamento nunca deve travar o update
        db.rollback()
        print(f"[PROPOSTA-VERSAO] erro ao arquivar versao da proposta {proposta.id}: {e}")

    # vendedor e imutavel: sempre o do criador, nunca sobrescrito por update.
    payload = dados.model_dump(exclude_unset=True, exclude={"itens", "aparelhos", "vendedor"})
    for k, v in payload.items():
        if v is None and k in NON_NULLABLE:
            continue
        setattr(proposta, k, v)
    if dados.itens is not None:
        _aplicar_itens(proposta, dados.itens)
    if dados.aparelhos is not None:
        _aplicar_aparelhos(db, proposta, dados.aparelhos)
    db.commit()
    db.refresh(proposta)
    return proposta


def montar_saida(db: Session, proposta: Proposta) -> PropostaOut:
    """Monta o `PropostaOut` calculando os totais e resolvendo o
    nome/documento do cliente (override editável na proposta tem prioridade
    sobre o cadastro do Cliente)."""
    total_itens = sum(float(i.total) for i in proposta.itens)
    total = total_itens + float(proposta.frete or 0) - float(proposta.desconto or 0)

    saida = PropostaOut.model_validate(proposta)
    saida.total_itens = round(total_itens, 2)
    saida.total = round(total, 2)

    ov = proposta.cliente_override or {}
    cliente = proposta.cliente_rel
    saida.cliente_nome = (ov.get("nome") or None) or (cliente.nome if cliente else None)
    saida.cliente_documento = (ov.get("documento") or None) or (
        (cliente.cgc or cliente.cpf) if cliente else None
    )
    return saida


def snapshot_proposta(proposta: Proposta) -> dict:
    """Snapshot exibível do estado atual da proposta (para o histórico de versões)."""
    total_itens = sum(float(i.total) for i in proposta.itens)
    total = total_itens + float(proposta.frete or 0) - float(proposta.desconto or 0)
    cliente = proposta.cliente_rel
    return {
        "numero": proposta.numero,
        "data": proposta.data.isoformat() if proposta.data else None,
        "cliente_nome": cliente.nome if cliente else None,
        "cliente_documento": (cliente.cgc or cliente.cpf) if cliente else None,
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
