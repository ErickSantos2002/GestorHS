# SSO Microsoft (Entra ID) — design

**Data:** 2026-08-31
**Status:** aprovado no brainstorming, aguardando revisão do Erick

## Problema

Entrar no GestorHS pelo `/app` exige e-mail e senha próprios do sistema. São **17
usuários ativos, todos `@healthsafetytech.com`** (conferido no banco de produção
em 2026-08-31) — ou seja, todo mundo já tem identidade corporativa no Entra ID e
mantém uma senha a mais só por causa do GestorHS. Senha a mais é senha
esquecida, senha repetida e senha redefinida na mão pelo administrador.

O HSGrowth CRM resolveu isso primeiro; o TaskHS repetiu em 2026-08-28
(`2026-08-28-sso-microsoft-design.md`, no repo do TaskHS). Este documento traz o
mesmo recurso para o GestorHS. O desenho do TaskHS é a referência direta — as
diferenças estão todas em "Decisões".

## Escopo

**Dentro:**

- Botão "Entrar com Microsoft" na tela de login **interna** (`/login` → `/app`).
- Endpoints de autorização, callback, troca de ticket e status no backend.
- Rota pública `/auth/callback` no frontend.
- Envs novas, `.env.example`, testes.

**Fora (de propósito):**

- **O portal do cliente (`/portal`).** Quem entra por lá é cliente externo,
  autenticado por CNPJ + login + senha, sem conta no nosso tenant. Nenhuma rota
  nova sob `/portal`.
- **Provisionamento automático.** Quem não tem `Usuario` no GestorHS não entra —
  volta para o `/login` com mensagem. O cadastro continua na tela de Usuários.
  Isso mantém o controle de acesso num lugar só e evita o tenant inteiro (não só
  as 17 pessoas) ganhando conta ao logar.
- **Qualquer uso do Graph além do login.** Escopo `User.Read`, apenas para ler o
  e-mail. O token da Microsoft é usado no callback e descartado; nenhuma coluna
  `ms_access_token`/`ms_refresh_token` em `usuarios`. O CRM guarda esses tokens
  porque manda e-mail e lê calendário pelo card — o GestorHS não faz nada disso,
  e guardar credencial que ninguém usa é só superfície de ataque.
- **Desligar o login por senha.** Os dois convivem. Se um dia o SSO for o único
  caminho, é decisão separada.
- **Auditoria de acesso.** O GestorHS não tem tabela de auditoria de login (só
  `log_os` e `log_integracao`, ambas de domínio). O TaskHS grava `AuditLog` no
  callback porque a tabela já existia lá. Criar uma aqui só para o SSO seria
  inventar um subsistema no meio de outro — fica como projeto à parte.

## Fluxo

```
LoginPage → GET /auth/microsoft                302 → login.microsoftonline.com
Microsoft → GET /auth/microsoft/callback?code=…
            troca code por token → GET /me no Graph → e-mail
            busca Usuario por email (normalizado):
              não achou  → 302 {FRONTEND_URL}/login?erro=usuario_nao_encontrado
              inativo    → 302 {FRONTEND_URL}/login?erro=usuario_inativo
              ok         → access (30 min) + refresh (7 d), os mesmos do
                           /auth/login, guardados sob um ticket opaco
                         → 302 {FRONTEND_URL}/auth/callback?ticket=<opaco>
Front /auth/callback → POST /auth/sso/exchange {ticket}
                     → Token {access_token, refresh_token}
                     → setTokens() + GET /auth/me → "/app"
```

A partir do `sso/exchange` não há nada de especial: os tokens são os mesmos que
o `POST /auth/login` devolve, e daí para frente a sessão é indistinguível — o
`/auth/refresh` renova igual.

## Decisões

### O JWT não passa pela URL

O CRM redireciona para `/auth/callback?access_token=…&refresh_token=…`. Token na
query string entra no histórico do navegador, no `Referer` da próxima
requisição e em qualquer log de proxy no caminho. Aqui é pior que no TaskHS: o
que vazaria é um **refresh token de 7 dias**, não um JWT de 8 horas.

Então o callback guarda o par sob um **ticket opaco de uso único** e manda só o
ticket na URL. O front troca o ticket pelos tokens num `POST`. Ticket já usado,
ou com mais de 60 s, é recusado com **400**.

400 e não 401 é de propósito: o cliente HTTP do front (`api.ts`) trata 401 como
sessão expirada — tenta o refresh, falha, limpa o `localStorage` e chama
`onUnauthorized`. A página de callback nunca chegaria a mostrar o que houve.

### Ticket em memória

`app/core/sso_tickets.py`: um `dict` de `ticket → (access, refresh, expira_em)`,
chave `secrets.token_urlsafe(32)`, TTL 60 s, `pop` na troca, varredura preguiçosa
dos vencidos a cada emissão. Sem tabela, sem Redis, sem migração.

**Isso assume processo único.** É uma premissa nova neste repo: hoje só o job
mensal do GrowthHS (`app/tarefas/vencendo.py`) depende de rodar num processo só,
e ele é idempotente por chave, então múltiplos workers duplicariam trabalho mas
não quebrariam. O ticket de SSO, não: com dois workers, o `exchange` cai num
processo que não emitiu o ticket e o login falha de forma intermitente. Se o
deploy um dia ganhar `--workers > 1`, a correção é estado compartilhado (Redis
ou uma tabela com TTL). Registrado aqui porque é o tipo de coisa que se descobre
tarde.

Reiniciar o backend descarta tickets pendentes — consequência: quem estava
exatamente no meio do redirect clica de novo.

### E-mail é a chave

A busca é `Usuario.email == emails.normalizar(email)`, o mesmo normalizador que o
`/auth/login` já usa. O e-mail vem do Graph em `mail` ou, se vier nulo, em
`userPrincipalName`.

`usuarios.email` é `NOT NULL UNIQUE` e já é a chave do login por senha — não há
campo "username" concorrente. Conferido em 2026-08-31: os 17 ativos são todos
`@healthsafetytech.com`, sem exceção. Usuário criado no futuro com e-mail de
outro domínio simplesmente não terá SSO — entra pela senha.

### SSO ignora `precisa_redefinir_senha`

O `/auth/login` devolve `LoginOut(precisa_redefinir=True)` e nega os tokens
enquanto a flag estiver ligada. O callback do SSO **não faz essa checagem**.

A flag existe para forçar a troca de uma senha própria — provisória, vazada ou
nunca definida. Quem entra por SSO não usou senha nenhuma, e mandá-lo para a
tela de redefinir senha exigiria criar uma credencial que ele não vai usar. A
flag continua valendo, intacta, para o caminho de senha.

### SSO desligável

As cinco envs nascem com default `""` no `config.py` e uma property `sso_ativo`
diz se **as cinco** estão preenchidas — `FRONTEND_URL` entra na conta porque sem
ela o callback não tem para onde redirecionar, e SSO meio configurado seria pior
que desligado. Com o SSO desligado o
`GET /auth/microsoft` responde 503 e o front esconde o botão — que ele descobre
por `GET /auth/sso/status` → `{"ativo": bool}`, endpoint público de uma linha. A
alternativa (um `VITE_SSO_ATIVO` no build do front) duplicaria a configuração em
duas pontas que podem discordar, ainda mais aqui, onde a URL da API já é
injetada em runtime pelo `/config.js`.

Assim quem sobe o projeto local sem app no Azure não vê nada quebrado, e o
`.env.example` vai para o repo com os campos em branco.

### MSAL síncrono, sem `to_thread`

O TaskHS precisou de `asyncio.to_thread(...)` porque os endpoints dele são
`async def` e a `msal` é bloqueante. **Aqui não:** todo o `app/api/auth.py` é
`def` comum, que o FastAPI já roda no threadpool. As chamadas da `msal` e o
`GET /me` do Graph (via `httpx.Client`, síncrono — `httpx` já está no
`requirements.txt`) entram diretas. Manter os endpoints novos como `def`, igual
aos vizinhos.

## Backend

| Arquivo | Ação |
|---|---|
| `requirements.txt` | `+ msal`, **sem pin** — o arquivo não pina nenhuma das 15 linhas. `httpx` já está lá |
| `app/core/config.py` | `+ MS_CLIENT_ID`, `MS_TENANT_ID`, `MS_CLIENT_SECRET`, `MS_REDIRECT_URI`, `FRONTEND_URL` — todos `str = ""`; `+ property sso_ativo` |
| `app/core/sso_tickets.py` | **criar** — `emitir(access, refresh) -> str`, `resgatar(ticket) -> tuple[str, str] \| None` |
| `app/integrations/microsoft_client.py` | **criar** — `url_de_autorizacao()`, `trocar_code_por_token(code)`, `email_do_usuario(access_token)` |
| `app/api/auth.py` | `+ GET /microsoft`, `+ GET /microsoft/callback`, `+ POST /sso/exchange`, `+ GET /sso/status` |
| `backend/.env.example` | `+` as cinco vars, **vazias** |

O cliente vai em `app/integrations/`, junto de `taskhs_client.py`,
`hsgrowth_client.py` e `enderecos_client.py` — I/O com serviço externo é
exatamente o que essa pasta guarda, e o sufixo `_client` é a convenção de lá.
Segue o feitio do `enderecos_client`: síncrono e com erro que sobe, porque o
usuário está esperando na tela (o `taskhs_client`, best-effort, engole tudo — não
é o caso aqui).

Os quatro endpoints são **públicos** — não podem depender de
`get_current_usuario`, já que o objetivo deles é justamente criar a sessão.

`POST /auth/sso/exchange` responde com o schema `Token` (não `LoginOut`): o SSO
nunca devolve `precisa_redefinir`, e `Token` é o que o front já consome em
`definirSenha`.

## Frontend

| Arquivo | Ação |
|---|---|
| `src/app/pages/AuthCallbackPage.tsx` | **criar** — troca o ticket; em erro, mensagem + "Voltar para o login" |
| `src/App.tsx` | `+` rota pública `/auth/callback`, fora do `ProtectedRoute` |
| `src/auth/AuthContext.tsx` | `+ entrarComTokens(tokens)` — reusa a persistência do login normal |
| `src/lib/api.ts` | `+ export apiUrl(path)` — devolve `${BASE_URL}${path}` |
| `src/app/pages/LoginPage.tsx` | divisor "ou" + botão com o logo Microsoft; lê `?erro=` e mostra a mensagem |

O botão é uma **âncora** com `href={apiUrl('/auth/microsoft')}`, não um `fetch`:
o fluxo é uma navegação de página inteira até a Microsoft, e XHR não segue
redirect cross-origin. O `apiUrl` existe porque `BASE_URL` hoje é privado do
`api.ts` e é resolvido em runtime pelo `window.__API_URL__` — a âncora precisa
do mesmo valor, e duplicar essa cascata numa segunda função seria pedir para as
duas discordarem.

`entrarComTokens` existe para o `AuthCallbackPage` não duplicar `setTokens` +
`GET /auth/me` + `setUser` — a hidratação da sessão fica num lugar só, como já é
hoje no `login`.

Mensagens de erro:

| `?erro=` | Texto |
|---|---|
| `usuario_nao_encontrado` | Nenhuma conta GestorHS para este e-mail Microsoft. Fale com o administrador. |
| `usuario_inativo` | Usuário desativado. Fale com o administrador. |
| `falha_microsoft` | Falha na autenticação com a Microsoft. Tente novamente. |

## Azure e deploy

App Registration **GestorHS** — próprio, não o do TaskHS. Um secret por sistema:
vazamento ou expiração de um não derruba o outro. Single tenant
(`healthsafetytech.com`), permissão delegada `User.Read` com admin consent.

Redirect URIs (tipo *Web*):

- `https://gestorhsapi.healthsafetytech.com/auth/microsoft/callback` (produção)
- `http://localhost:8000/auth/microsoft/callback` (dev)

Sem `/api` no caminho: o router é `APIRouter(prefix="/auth")` e o `main.py` não
monta prefixo nenhum — o front chama `https://gestorhsapi…/auth/login` direto.
Essa é a diferença mais fácil de errar ao copiar do TaskHS, que tem `/api`.

Envs de produção (Easypanel, serviço backend):

```
MS_CLIENT_ID=…
MS_TENANT_ID=…
MS_CLIENT_SECRET=…
MS_REDIRECT_URI=https://gestorhsapi.healthsafetytech.com/auth/microsoft/callback
FRONTEND_URL=https://gestorhs.healthsafetytech.com
```

Para testar na máquina, apontar `MS_REDIRECT_URI` para a variante `localhost`
(já cadastrada) e `FRONTEND_URL` para `http://localhost:5173`.

O client secret vive só no `.env` (gitignorado) e no Easypanel — **nunca** em
arquivo versionado, incluindo este documento. Expira em 24 meses; renovar é
gerar outro no portal e atualizar as duas pontas.

**O serviço backend do GestorHS tem que ficar em 1 réplica, sem `--workers`.**
O ticket do SSO é estado em memória (ver `sso_tickets.py`): com duas réplicas o
login passa a falhar em cerca de metade das tentativas com "Link de acesso
inválido ou expirado", e nada no log aponta para a causa — o pedido caiu numa
réplica que nunca emitiu aquele ticket. No Easypanel, subir réplicas é um
botão — por isso precisa estar escrito aqui, não só na seção de desenho.

**`BACKEND_CORS_ORIGINS` precisa conter `https://gestorhs.healthsafetytech.com`**,
senão o `POST /auth/sso/exchange` morre no preflight e o usuário volta para o
login sem mensagem.

**Nota de offboarding:** ligar o SSO não faz do Entra ID o kill switch.
Desativar a conta Microsoft de quem sai bloqueia o SSO, mas **não** o login
por senha, que continua em paralelo por desenho. O desligamento continua
sendo `ativo=False` na tela de Usuários do GestorHS.

**Nota de log:** tanto o `?code=` (da Microsoft) quanto o `?ticket=` (do
redirect interno) aparecem em log de acesso de proxy. Os dois são de uso
único e de vida curta (o ticket, 60 s), então o risco é baixo — mas quem
cuidar do proxy deve saber.

## Verificação

O projeto tem suíte de testes, então boa parte é automática (TDD: teste antes).

**pytest** (`backend/tests/test_sso_microsoft.py`):

1. Ticket resgatado uma vez devolve o par; o segundo resgate devolve `None`.
2. Ticket com mais de 60 s devolve `None`.
3. `POST /auth/sso/exchange` com ticket inválido/usado/expirado → **400**.
4. `GET /auth/sso/status` → `{"ativo": false}` com envs vazias, `true` com elas
   preenchidas.
5. `GET /auth/microsoft` com SSO desligado → **503**.
6. Callback (Graph mockado) com e-mail sem `Usuario` → 302 para
   `…/login?erro=usuario_nao_encontrado`.
7. Callback com `Usuario.ativo=False` → 302 com `erro=usuario_inativo`.
8. Callback com `Usuario` válido e `precisa_redefinir_senha=True` → 302 para
   `/auth/callback?ticket=…` (a flag **não** bloqueia).
9. Os testes de `/auth/login` existentes continuam passando — inclusive o que
   exige `precisa_redefinir`.

**vitest** (`frontend/src/pages/AuthCallbackPage.test.tsx`):

10. Ticket válido → chama o exchange, persiste e navega para `/app`.
11. Exchange 400 → mostra mensagem e o link de voltar, sem navegar.

**Manual, depois do app no Azure:**

12. Fluxo feliz no navegador: botão → conta corporativa → volta logado, nome
    certo no cabeçalho.
13. Login por e-mail e senha continua funcionando.
14. `npm run lint && npx tsc -b --noEmit && npm run build` passa.

## Notas relacionadas

- `2026-08-28-sso-microsoft-design.md` (repo TaskHS) — a implementação irmã.
- `MICROSOFT365_INTEGRACAO.md` (repo hsgrowth-sistema) — a primeira da casa.
- [Fundação de auth do backend](../plans/2026-06-01-backend-fundacao-auth.md) — o
  login por senha e os tokens que o SSO reusa sem tocar.
