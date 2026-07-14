# Acesso: login por e-mail + desativar usuário

**Data:** 2026-07-13
**Status:** aprovado (brainstorming)

## Objetivo

Duas mudanças na área de **Acesso/Usuários** (aplicação interna):

1. **Login por e-mail.** O usuário passa a entrar com o e-mail em vez do `login`
   (apelido). O e-mail vira o identificador: **obrigatório e único**. A coluna
   `login` é removida.
2. **Desativar em vez de excluir.** Excluir usuário hoje **quebra** (bug); a
   correção é desativar (soft delete), preservando o histórico de auditoria.

O **portal do cliente não muda** — ele autentica por documento + login + senha
numa tabela separada (`usuarios_cliente`).

## Bug corrigido: exclusão de usuário (causa raiz)

Evidência (log do backend, produção):

```
DELETE /usuarios/7 → 500 Internal Server Error
psycopg2.errors.ForeignKeyViolation: update or delete on table "usuarios"
violates foreign key constraint "logs_os_usuario_fkey" on table "logs_os"
```

Três tabelas referenciam `usuarios.id`: `logs_os.usuario`,
`solicitacoes.atendido_por`, `transferencias_equipamento.usuario`. Como qualquer
pessoa que já tocou numa OS tem log, **nenhum usuário real é excluível** — o
`db.delete()` estoura a FK e o erro vaza como 500.

**Decisão:** não excluir de verdade (destruiria a rastreabilidade de quem fez cada
OS, algo que importa num sistema de calibração). Em vez disso, **desativar**, com o
rótulo explícito na UI ("Desativar", não "Excluir").

## Estado dos dados (verificado em produção)

5 usuários, **todos com e-mail preenchido e sem duplicatas** — logo, tornar o
e-mail `NOT NULL` + `UNIQUE` é seguro e não exige backfill manual.

## Backend

### Dependência nova — `requirements.txt`
`EmailStr` (Pydantic v2) exige o pacote **`email-validator`**, que **não está
instalado** hoje (verificado: `ImportError: email-validator is not installed`).
Trocar `pydantic` por **`pydantic[email]`** no `requirements.txt`.

**Consequência de deploy:** a imagem Docker precisa ser **reconstruída**
(local: `docker compose build backend`; em produção, o Easypanel reconstrói a partir
do `requirements.txt` no próximo deploy). Sem o rebuild, a API não sobe (ImportError
no import do schema).

### Modelo — `app/models/usuario.py`
- `email`: `String(200)`, **`nullable=False`, `unique=True`**.
- `ativo`: `Boolean`, `nullable=False`, `default=True` (novo).
- **Remover** a coluna `login`.

### Migração — `0011_usuario_email_login_ativo.py`
Ordem do `upgrade`:
1. Normalizar os e-mails existentes: `UPDATE usuarios SET email = lower(trim(email))`.
2. `ALTER COLUMN email SET NOT NULL` + criar índice único `uq_usuarios_email`.
3. `ADD COLUMN ativo boolean NOT NULL DEFAULT true`.
4. `DROP COLUMN login`.

`downgrade`: recria `login` (nullable), remove `ativo`, remove a unique de `email`
e volta `email` a nullable.

### Autenticação — `app/api/auth.py`
- `POST /auth/login`: busca por **e-mail** (`Usuario.email == email_normalizado`).
  Normalização = `strip()` + `lower()` (comparação case-insensitive).
- `POST /auth/definir-senha`: idem (identifica por e-mail).
- **Usuário desativado**: senha correta porém `ativo = false` → **403** com
  `"Usuário desativado. Fale com o administrador."` (mensagem clara; é um sistema
  interno). Credencial inexistente ou senha errada continuam **401 "Credenciais
  inválidas"**, com o timing achatado (anti-enumeração) que já existe.
- `POST /auth/refresh`: além das checagens atuais, **nega (401) se o usuário estiver
  desativado** — senão um desativado continuaria operando até o token expirar.

### Autorização — `app/api/deps.py`
- `get_current_usuario`: **401 se o usuário estiver desativado**. Fecha a janela do
  access token já emitido (a desativação passa a valer na hora).

### Schemas — `app/schemas/auth.py` e `app/schemas/acesso.py`
- `LoginRequest`: campo `login` → **`email`**.
- `DefinirSenhaIn`: campo `login` → **`email`**.
- `UsuarioCreate`: **remove `login`**; `email: EmailStr` (obrigatório, validado);
  mantém `nome`, `senha` (min 8), `funcao_id`.
- `UsuarioUpdate`: remove `login`; `email: Optional[EmailStr]`.
- `UsuarioListOut`: remove `login`; adiciona **`ativo: bool`**.

### Usuários — `app/api/usuarios.py`
- `POST /usuarios` (criar): unicidade agora no **e-mail** →
  **409 "e-mail já em uso"**. E-mail normalizado (trim/lower) antes de gravar.
- `PATCH /usuarios/{id}`: idem para troca de e-mail (409 se duplicado).
- `GET /usuarios`: novo parâmetro **`incluir_inativos: bool = False`** — por padrão
  lista só os ativos.
- **Remover** `DELETE /usuarios/{id}`.
- **Novo** `POST /usuarios/{id}/desativar` (204): guardas — **não pode desativar a si
  mesmo** (400) nem o **último administrador ativo** (400). Idempotente: desativar
  quem já está inativo é no-op 204.
- **Novo** `POST /usuarios/{id}/reativar` (204).
- `_conta_admins` passa a contar **apenas administradores ativos** (senão a guarda do
  "último admin" seria burlada por admins desativados).

### Script — `app/scripts/criar_usuario.py`
Passa a receber **e-mail** em vez de login: `python -m app.scripts.criar_usuario <email> <senha> <Funcao>`.
Continua idempotente (busca por e-mail).

## Frontend

### Login — `src/app/pages/LoginPage.tsx` + `src/auth/AuthContext.tsx` + `src/lib/api.ts`
- O campo "Usuário" vira **"E-mail"** (`type="email"`, `autocomplete="username"`).
- `login(email, senha)` e `definirSenha(email, ...)` — o corpo enviado passa a ter
  a chave `email`.
- Erro **403 de usuário desativado** é exibido com a mensagem do backend (não como
  "credenciais inválidas").

### Usuários — página de administração
- Formulário de criar/editar: **Nome · E-mail · Senha · Função** (sem campo Login).
  E-mail obrigatório, com validação de formato; 409 exibe "e-mail já em uso".
- A lista mostra **Nome · E-mail · Função** (a coluna Login some).
- O botão de excluir vira **"Desativar"**, com confirmação deixando claro que o
  usuário perde o acesso mas **o histórico das OS é preservado**.
- Usuários desativados ficam **ocultos por padrão**; um toggle **"Mostrar
  desativados"** os revela (com badge "Desativado") e habilita **"Reativar"**
  (mesmo padrão já usado na página de Caixas).

## Testes

- **Auth** (`test_auth.py`, reescrito): login com e-mail correto; e-mail
  inexistente → 401; senha errada → 401; e-mail com espaços/maiúsculas funciona
  (case-insensitive); usuário desativado → **403** com a mensagem; refresh de
  desativado → 401; `definir-senha` por e-mail.
- **Deps**: access token de usuário desativado → 401 em rota protegida.
- **Usuários** (`test_acesso.py`, reescrito): criar exige e-mail (422 sem e-mail;
  422 e-mail inválido); e-mail duplicado → 409; listar oculta inativos por padrão e
  `incluir_inativos=true` os traz; desativar (204) — a si mesmo → 400; último admin
  ativo → 400; reativar (204); **`DELETE /usuarios/{id}` não existe mais** (405/404).
- **Rastreabilidade**: uma OS com log do usuário continua íntegra após desativá-lo
  (o log segue apontando pro usuário).
- **Varredura mecânica**: os 31 outros arquivos de teste que autenticam via
  `/auth/login` passam a mandar `{"email": ...}` com os e-mails já existentes nas
  fixtures (`admin@hs.com`, `comum@hs.com`, `lab@hs.com`, `fin@hs.com`,
  `comercial@hs.com`). As fixtures do `conftest.py` perdem o `login=` e ganham
  `ativo=True` por default.

## Changelog

Entrada **v1.12.0** — login por e-mail, e-mail obrigatório no cadastro de usuário, e
"Desativar" no lugar de "Excluir" (com o histórico preservado).

## Aplicação em produção

1. **Rebuild da imagem** do backend (por causa do `email-validator` novo). Sem isso a
   API não sobe.
2. `alembic upgrade head` (migração 0011 — normaliza e-mails, aplica NOT NULL/UNIQUE,
   adiciona `ativo`, remove `login`). **Requer consentimento — DDL em produção.**
3. Depois da migração, **todos entram com o e-mail** (o `login` antigo deixa de valer).
   Os 5 e-mails atuais já estão cadastrados.

## Fora de escopo

- Login do portal do cliente (segue por documento + login + senha).
- Recuperação de senha por e-mail / envio de e-mail.
- Corrigir os 3 usuários sem função (`jccunhaaraujo`, `nicholson`, `lidisay`) —
  anotado como follow-up separado.
- Exclusão definitiva (hard delete) de usuários.
