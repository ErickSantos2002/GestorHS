"""Publica o modelo HTML do Relatorio de Manutencao no banco.

O modelo vive em `docs/certificado-manutencao/modelo-relatorio-manutencao.html`
(versionado, revisavel em diff) e PRECISA ser copiado para `certificados` — e' de
la que o motor le na hora de gerar. Sem este script a copia era manual, colando
o HTML na tela de Modelos, e as duas versoes divergiam em silencio.

Grava sempre no modelo GENERICO (equipamento nulo, tipo M): manutencao tem um
modelo unico para todos os aparelhos.

    python -m app.scripts.publicar_modelo_manutencao              # so compara
    python -m app.scripts.publicar_modelo_manutencao --aplicar    # grava
"""
import argparse
import difflib
import io
from pathlib import Path

from app.models import CertificadoModelo
from app.models.database import SessionLocal

ARQUIVO = Path(__file__).resolve().parents[3] / "docs" / "certificado-manutencao" / "modelo-relatorio-manutencao.html"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--aplicar", action="store_true", help="grava de fato (sem isso, so compara)")
    args = p.parse_args()

    if not ARQUIVO.exists():
        print(f"arquivo nao encontrado: {ARQUIVO}")
        return
    texto = io.open(ARQUIVO, encoding="utf-8").read()

    db = SessionLocal()
    try:
        modelo = (
            db.query(CertificadoModelo)
            .filter(CertificadoModelo.equipamento.is_(None), CertificadoModelo.tipo == "M")
            .first()
        )
        atual = (modelo.texto or "") if modelo else ""
        print(f"arquivo: {len(texto)} chars   banco: {len(atual)} chars")
        if atual.strip() == texto.strip():
            print("ja estao identicos — nada a fazer")
            return

        diff = list(difflib.unified_diff(
            atual.splitlines(), texto.splitlines(), "banco", "arquivo", lineterm="", n=1))
        print(f"diferencas: {len(diff)} linhas")
        for linha in diff[:40]:
            print("  ", linha[:150])

        if not args.aplicar:
            print("\n(comparacao — rode com --aplicar para gravar)")
            return

        if modelo is None:
            modelo = CertificadoModelo(equipamento=None, tipo="M")
            db.add(modelo)
        modelo.texto = texto
        db.commit()
        print("\ngravado no banco")
    finally:
        db.close()


if __name__ == "__main__":
    main()
