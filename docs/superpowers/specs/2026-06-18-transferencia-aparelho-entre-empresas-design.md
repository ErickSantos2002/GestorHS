# Spec — Transferência de aparelho entre empresas

**Data:** 2026-06-18
**Status:** Aprovado (aguardando revisão final do spec)

## Problema

Não há como transferir um aparelho (`equipamento_cliente`) de uma empresa
(`cliente`) para outra. Quando um aparelho muda de dono, hoje seria preciso
recadastrar — perdendo histórico, calibração e certificados.

## Por que é simples no modelo atual

- O dono do aparelho é a coluna `equipamento_cliente.cliente`. **Transferir =
  trocar essa coluna.**
- A `Ordem` guarda `cliente` **independentemente** do aparelho (coluna própria,
  não-nula). As OS antigas continuam apontando para a empresa antiga → o
  histórico **não quebra**. O mesmo vale para `Solicitacao` (tem `cliente` próprio).
- O **portal isola por `cliente`** (`EquipamentoCliente.cliente == cli.cliente` e
  `Ordem.cliente == cli.cliente`), então trocar o dono move o aparelho para o
  portal da nova empresa automaticamente, sem mexer nas OS antigas.
- Calibração, série, patrimônio e datas vivem na linha do aparelho → **viajam
  com ele** (é o mesmo aparelho físico).

## Decisões (aprovadas)

- Bloquear a transferência se o aparelho tiver **OS ativa** (fase 4-7).
- **Registrar** cada transferência numa **tabela de auditoria** dedicada, exibida
  na ficha do aparelho.
- Permissão: **somente `Administrador`** (mesma regra das outras escritas de
  aparelho).
- A transferência troca o dono e **zera `os_atual`** (que fica obsoleto após a
  troca; ele só é escrito ao abrir OS e nunca limpo).

## Escopo

**Inclui:** tabela/migração de auditoria, endpoint de transferência, endpoint de
listagem das transferências, botão + modal no frontend (com busca de empresa) e
seção "Transferências" na ficha do aparelho.

**Não inclui (YAGNI):** transferência em massa; desfazer transferência;
transferência pelo portal (é ação interna); mover OS antigas para o novo dono
(elas devem permanecer com a empresa da época).

## Design

### 1. Modelo + migração (`0009_transferencias_equipamento`)

Nova tabela **`transferencias_equipamento`**:

| Coluna | Tipo | Nota |
|--------|------|------|
| `id` | Integer PK | |
| `equipamento_cliente` | FK → equipamentos_cliente.id, NOT NULL | o aparelho |
| `de_cliente` | FK → clientes.id, NOT NULL | dono anterior |
| `para_cliente` | FK → clientes.id, NOT NULL | novo dono |
| `data` | DateTime(timezone=True), NOT NULL | quando (UTC) |
| `usuario` | FK → usuarios.id, nullable | quem fez |
| `obs` | Text, nullable | motivo/observação |

Modelo SQLAlchemy `TransferenciaEquipamento` em
`backend/app/models/transferencia_equipamento.py`, registrado em
`models/__init__.py`. Migração Alembic `0009` cria a tabela (segue o padrão
`NNNN_descricao.py`).

### 2. Backend — endpoints (`api/equipamentos_cliente.py`)

**`POST /equipamentos-cliente/{id}/transferir`** — body
`TransferirIn { cliente: int (destino), obs: str | None }`.
Protegido por `require_funcao("Administrador")`.

Ordem de validação:
1. aparelho existe → senão 404.
2. cliente destino existe → senão 404 "cliente destino não encontrado".
3. destino ≠ dono atual → senão 400 "aparelho já pertence a este cliente".
4. **sem OS ativa** (existe `Ordem` do aparelho com `fase in ATIVAS`) → senão
   409 "finalize ou cancele a OS ativa antes de transferir".
5. sucesso: cria `TransferenciaEquipamento(equipamento_cliente=id,
   de_cliente=<atual>, para_cliente=<destino>, data=agora(), usuario=<user>,
   obs=...)`; faz `ec.cliente = destino`; `ec.os_atual = None`; commit; retorna o
   aparelho atualizado (mesmo schema de saída usado pelo GET/PATCH de aparelho —
   confirmar o nome exato na fase de plano).

A lógica de "tem OS ativa" reusa o critério de fases ativas do workflow
(`os_workflow.ATIVAS`), como o endpoint `abrir` já faz.

**`GET /equipamentos-cliente/{id}/transferencias`** →
`list[TransferenciaOut]` ordenado por `data` desc, com nomes resolvidos:
`{ id, data, de_cliente, de_cliente_nome, para_cliente, para_cliente_nome,
usuario_nome, obs }`. Leitura liberada para usuário interno autenticado
(`get_current_usuario`), como os outros GET de aparelho.

Schemas novos em `backend/app/schemas/frota.py`: `TransferirIn`,
`TransferenciaOut`.

### 3. Frontend

- **API** (`src/app/frota/api.ts`): `transferir(id, { cliente, obs })` (POST) e
  `transferencias(id)` (GET → `Transferencia[]`); tipo `Transferencia`.
- **Ficha do aparelho** (`EquipamentoClienteDetailPage.tsx`):
  - Botão **"Transferir"** ao lado de "Excluir" (visível só para Admin —
    `isAdmin(user)`). Desabilitado quando há OS em andamento (reusa o
    `osAtiva(ordens)` já existente), com dica "Finalize a OS antes de transferir".
  - **Modal de transferência**: campo de **busca de empresa** (consulta o endpoint
    de listagem de clientes com `q`, nos moldes da busca de caixa no
    `AbrirOSModal`) para escolher o destino + observação opcional. Ao confirmar,
    chama `transferir` e recarrega a ficha.
  - Nova seção **"Transferências"** (no aside, como Histórico/OS/Certificados):
    tabela com Data · De → Para · Usuário · Obs.
- O modal de transferência fica em um arquivo próprio
  (`src/app/frota/TransferirModal.tsx`) para manter a página focada.

### 4. Testes

**Backend** (`tests/test_frota_transferencia.py`):
- transfere: muda `ec.cliente`, zera `os_atual`, cria 1 registro de auditoria.
- bloqueia com OS ativa → 409.
- cliente destino inexistente → 404.
- destino igual ao atual → 400.
- exige Administrador → 403 para outra função.
- **OS antigas mantêm o cliente antigo** após a transferência (não vazam para o
  novo dono); o portal do dono **novo** vê o aparelho, o portal do **antigo** não.
- `GET /transferencias` lista o histórico com nomes resolvidos.

**Frontend**:
- `api.ts`: chamadas `transferir`/`transferencias` montam URL/método corretos
  (nível de cliente de API, padrão dos testes existentes).
- Estado do botão "Transferir" (habilitado/desabilitado conforme OS ativa) se
  viável sem teste de render pesado; caso contrário, verificação visual no app.

## Changelog

Ao concluir, adicionar entrada em
`frontend/src/app/changelog/data.ts` (nova versão) descrevendo a transferência de
aparelho entre empresas.
