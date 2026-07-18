"""Montagem pura do payload de card do GrowthHS a partir de entidades do GestorHS.

Sem I/O: as funções aqui recebem objetos já carregados (cliente, equipamento_cliente,
elo) e devolvem apenas dicts prontos para o client de integração. Quem consulta o banco
é o chamador (fora deste módulo).
"""
from datetime import date
from typing import Optional


def _texto(valor) -> Optional[str]:
    """Normaliza para string não-vazia ou None (trata espaços em branco como vazio)."""
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None


def _data_iso(valor: Optional[date]) -> Optional[str]:
    if valor is None:
        return None
    return valor.strftime("%Y-%m-%d")


def montar_cliente(cliente) -> dict:
    """Monta o payload `client` do card do GrowthHS a partir de um cliente do GestorHS."""
    # external_id é sempre o id interno do cliente (str(cliente.id)), NUNCA o
    # CPF/CNPJ: documento não é único no cadastro do GestorHS (duplicidade de
    # cadastro, matriz/filial, digitação divergente), então casar por
    # documento juntaria clientes diferentes no GrowthHS. O id é a única
    # chave estável.
    document = _texto(getattr(cliente, "cgc", None)) or _texto(getattr(cliente, "cpf", None))

    partes_endereco = [
        _texto(getattr(cliente, "endereco", None)),
    ]
    numero = _texto(getattr(cliente, "numero", None))
    if numero:
        partes_endereco.append(numero)
    bairro = _texto(getattr(cliente, "bairro", None))
    if bairro:
        partes_endereco.append(bairro)
    partes_endereco = [p for p in partes_endereco if p]
    address = ", ".join(partes_endereco) if partes_endereco else None

    phone = (
        _texto(getattr(cliente, "celular", None))
        or _texto(getattr(cliente, "whatsapp", None))
        or _texto(getattr(cliente, "telefones", None))
    )

    return {
        "external_id": str(cliente.id),
        "name": _texto(getattr(cliente, "nome", None)),
        "document": document,
        "email": _texto(getattr(cliente, "email", None)),
        "phone": phone,
        "address": address,
        "city": _texto(getattr(cliente, "municipio", None)),
        "state": _texto(getattr(cliente, "estado", None)),
    }


def montar_contato(cliente) -> Optional[dict]:
    """Monta o payload `contact` a partir de `cliente.contato`; None se sem nome."""
    nome = _texto(getattr(cliente, "contato", None))
    if not nome:
        return None

    phone = (
        _texto(getattr(cliente, "celular", None))
        or _texto(getattr(cliente, "whatsapp", None))
        or _texto(getattr(cliente, "telefones", None))
    )

    return {
        "name": nome,
        "email": _texto(getattr(cliente, "email", None)),
        "phone": phone,
    }


def montar_device(ec, equipamento_desc: str, elo=None) -> dict:
    """Monta um item de `devices[]` a partir de um equipamento_cliente e, opcionalmente,
    do elo (Phoebus) em que o módulo está instalado.

    Com elo: o cliente reconhece o APARELHO (Phoebus), não o número do módulo — o
    serial_number vai o serial do Phoebus e o alcohol_module leva o serial do módulo.
    Sem elo: o próprio equipamento é o serial_number e não há alcohol_module.
    """
    if elo is not None:
        serial_number = elo.serie
        model = elo.descricao
        alcohol_module = ec.serie
    else:
        serial_number = ec.serie
        model = equipamento_desc
        alcohol_module = None

    return {
        "serial_number": serial_number,
        "model": model,
        "alcohol_module": alcohol_module,
        "next_recalibration_date": _data_iso(getattr(ec, "prox_calibragem", None)),
    }
