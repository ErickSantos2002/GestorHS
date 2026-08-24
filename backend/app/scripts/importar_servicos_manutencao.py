"""Leva os servicos do catalogo COMERCIAL para o catalogo de MANUTENCAO.

O relatorio de manutencao so aceita servico da lista fechada em
`manutencao_servicos`, que nasce vazia. Os servicos ja existem em `servicos`
(o catalogo das propostas), com o mesmo codigo que a equipe usa no dia a dia —
entao a carga le de la em vez de alguem redigitar 52 linhas.

O `resumo_padrao` entra VAZIO. Ele e' a frase que compoe o "Resumo do Servico"
do relatorio, e ninguem alem do laboratorio sabe redigi-la. Enquanto estiver
vazio o relatorio funciona, mas o resumo nasce em branco e o tecnico escreve a
mao — o preenchimento e' feito depois, pela tela.

Idempotente: pula o que ja existe, por codigo ou por descricao.

    python -m app.scripts.importar_servicos_manutencao              # so simula
    python -m app.scripts.importar_servicos_manutencao --aplicar    # grava
"""
import argparse

from app.models import ManutencaoServico, Servico
from app.models.database import SessionLocal


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--aplicar", action="store_true", help="grava de fato (sem isso, so simula)")
    args = p.parse_args()

    db = SessionLocal()
    try:
        existentes = db.query(ManutencaoServico).all()
        codigos = {s.codigo for s in existentes if s.codigo}
        descricoes = {(s.descricao or "").strip().upper() for s in existentes}

        novos, pulados = [], []
        for s in db.query(Servico).order_by(Servico.nome).all():
            codigo = (s.sku or "").strip() or None
            descricao = (s.nome or "").strip()
            if not descricao:
                continue
            if codigo and codigo in codigos:
                pulados.append((codigo, descricao, "codigo ja cadastrado"))
                continue
            if descricao.upper() in descricoes:
                pulados.append((codigo, descricao, "descricao ja cadastrada"))
                continue
            novos.append((codigo, descricao))
            # Reserva dentro do proprio lote: `descricao` e' UNICA, e a origem
            # pode ter duas linhas que so diferem em espaco ou caixa.
            if codigo:
                codigos.add(codigo)
            descricoes.add(descricao.upper())

        print(f"servicos no catalogo comercial: {db.query(Servico).count()}")
        print(f"ja no catalogo de manutencao:   {len(existentes)}")
        print(f"a inserir:                      {len(novos)}")
        print(f"pulados:                        {len(pulados)}")
        print()
        for codigo, descricao in novos:
            print(f"   + {str(codigo or '-'):>5}  {descricao}")
        for codigo, descricao, motivo in pulados:
            print(f"   . {str(codigo or '-'):>5}  {descricao}  ({motivo})")

        if not args.aplicar:
            print("\n(simulacao — rode com --aplicar para gravar)")
            return

        for codigo, descricao in novos:
            db.add(ManutencaoServico(codigo=codigo, descricao=descricao,
                                     resumo_padrao="", ativo=True))
        db.commit()
        print(f"\ngravados: {len(novos)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
