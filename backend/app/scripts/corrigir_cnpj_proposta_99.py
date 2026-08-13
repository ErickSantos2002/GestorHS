"""Coloca na proposta 99 o CNPJ da filial que se perdeu no painel de override.

Pontual e de uso unico: o CNPJ 01.258.944/0005-50 foi digitado em 13/08/2026 e
descartado sem aviso ao fechar o painel "Editar dados nesta proposta" (defeito
corrigido em v1.38.0). Este script apenas repoe o valor, preservando os campos
que ja estavam no override.

Escreve direto na coluna, sem passar por `atualizar_proposta`, para nao criar
uma versao nova nem arquivar um PDF de uma correcao que e' so um conserto de
dado. Idempotente: rodar de novo nao muda nada.

    python -m app.scripts.corrigir_cnpj_proposta_99            # so mostra
    python -m app.scripts.corrigir_cnpj_proposta_99 --aplicar  # grava
"""
import argparse
import json

from app.models.database import SessionLocal
from app.models import Proposta

NUMERO = 99
DOCUMENTO = "01258944000550"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--aplicar", action="store_true", help="grava de fato (sem isso, so simula)")
    args = p.parse_args()

    db = SessionLocal()
    try:
        proposta = db.query(Proposta).filter(Proposta.numero == NUMERO).one_or_none()
        if proposta is None:
            print(f"proposta {NUMERO} nao encontrada")
            return

        atual = dict(proposta.cliente_override or {})
        print("ANTES: ", json.dumps(atual, ensure_ascii=False))
        if atual.get("documento") == DOCUMENTO:
            print("documento ja esta correto — nada a fazer")
            return

        novo = {**atual, "documento": DOCUMENTO}
        print("DEPOIS:", json.dumps(novo, ensure_ascii=False))
        if not args.aplicar:
            print("\n(simulacao — rode com --aplicar para gravar)")
            return

        proposta.cliente_override = novo
        db.commit()
        db.refresh(proposta)
        print("gravado:", json.dumps(proposta.cliente_override, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()
