"""Cria ou atualiza um usuário interno com senha em hash.

Uso: python -m app.scripts.criar_usuario <email> <senha> [funcao]
"""
import sys
from app.models.database import SessionLocal
from app.models import Usuario, Funcao
from app.core.security import hash_senha
from app.core import emails


def main():
    if len(sys.argv) < 3:
        print("Uso: python -m app.scripts.criar_usuario <email> <senha> [funcao]")
        sys.exit(1)
    email, senha = emails.normalizar(sys.argv[1]), sys.argv[2]
    funcao_desc = sys.argv[3] if len(sys.argv) > 3 else "Administrador"

    db = SessionLocal()
    try:
        funcao = db.query(Funcao).filter(Funcao.descricao == funcao_desc).first()
        if funcao is None:
            print(f"Função '{funcao_desc}' não encontrada. Rode a migração 0001 primeiro.")
            sys.exit(1)
        usuario = db.query(Usuario).filter(Usuario.email == email).first()
        if usuario is None:
            usuario = Usuario(email=email, nome=email)
            db.add(usuario)
        usuario.senha = hash_senha(senha)
        usuario.precisa_redefinir_senha = False
        usuario.ativo = True
        usuario.funcao_id = funcao.id
        db.commit()
        print(f"Usuário '{email}' pronto com função '{funcao_desc}'.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
