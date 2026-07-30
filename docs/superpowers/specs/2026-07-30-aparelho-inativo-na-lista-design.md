# Aparelho inativo visível na lista — Design

**Data:** 2026-07-30
**Área:** backend (`api/equipamentos_cliente.py`) + frontend (`app/frota/FrotaPage.tsx`, `app/frota/api.ts`, `app/clientes/ClienteEquipamentosTab.tsx`) + testes.
**Tipo:** feature pequena (indicador visual + filtro). Sem migração.

## Problema

A lista interna de aparelhos **não distingue ativo de inativo**. O endpoint `GET /equipamentos-cliente` não filtra por `ativo` — devolve tudo misturado, e a tabela não mostra nada a respeito.

Em produção são **1.624 aparelhos inativos de 8.727** — cerca de **1 em cada 5 linhas** da lista é um aparelho aposentado, hoje indistinguível dos demais. Pior: o inativo continua exibindo o badge de calibração, então um aparelho fora de uso aparece em vermelho como **"Vencido"**, parecendo trabalho pendente numa fila que já não existe.

Contexto de nomenclatura que restringe o desenho: a coluna existente chamada **"Status"** é o status de **calibração** (`Em dia`/`Vencendo`/`Vencido`/`Sem data`), e o filtro ao lado dela também se chama "Status". A palavra **"Situação"** acabou de ser aposentada na v1.33.1 (era o campo morto A/I/M). Nenhuma das duas pode ser reusada para este indicador sem ressuscitar a confusão que a v1.33.1 desfez.

## Design

### 1. Backend — filtro opcional na listagem

`GET /equipamentos-cliente` ([api/equipamentos_cliente.py](../../../backend/app/api/equipamentos_cliente.py), função `listar`) ganha o parâmetro:

```python
ativo: bool | None = None
```

- **omitido** → todos (é o comportamento de hoje, preservado)
- `true` → só ativos
- `false` → só inativos

Aplicado como `query = query.filter(EquipamentoCliente.ativo.is_(ativo))` quando não é `None`. É o único ponto do backend tocado: os schemas de leitura já devolvem `ativo`, então a forma da resposta não muda.

### 2. Frota — filtro na barra de busca

Um segundo `Select` ao lado do filtro de calibração em [FrotaPage.tsx](../../../frontend/src/app/frota/FrotaPage.tsx), rotulado **"Aparelhos"**, com as opções *Todos* (padrão), *Ativos* e *Inativos*.

O rótulo é deliberado: **não** é "Status" (já ocupado pelo filtro de calibração, logo ao lado) e **não** é "Situação" (palavra aposentada na v1.33.1). Trocar o filtro zera o `offset` da paginação, como o filtro de calibração já faz.

O padrão é *Todos* — a lista abre exatamente como abre hoje. Esconder inativo por padrão foi considerado e descartado: quem procura um aparelho antigo pela busca estranharia não encontrá-lo.

### 3. A linha — Frota e aba Equipamentos do cliente

Quando `ativo === false`:

- **Selo** `<Badge tone="neutral">Inativo</Badge>` ao lado do nome do aparelho, na primeira coluna. O tom `neutral` já existe no componente `Badge` (cinza) — nenhum estilo novo.
- **Linha esmaecida**: a classe `opacity-60` entra no `<tr>`, somada às que já estão lá (`hover:bg-background-elevated transition-colors cursor-pointer`). Escolhida por ser uma classe única e verificável em teste, sem tocar no componente `Table`.

Aparelho **ativo não ganha selo nenhum** — a lista continua idêntica à de hoje para os ~80% ativos, e o olho vai direto na exceção. Não há coluna nova: a tabela já tem 5 colunas, e uma sexta com selo repetido em 80% das linhas seria ruído.

A aba Equipamentos do cliente ([ClienteEquipamentosTab.tsx](../../../frontend/src/app/clientes/ClienteEquipamentosTab.tsx)) recebe **o mesmo selo e o mesmo esmaecido**, para as duas telas não divergirem. Ela **não** recebe o filtro: não tem barra de filtros hoje, e criar uma só para isso é mais tela do que o problema pede.

### 4. Badge de calibração de aparelho inativo

Quando o aparelho está inativo, o badge de calibração vai para o tom **`neutral`**, mantendo o texto. "Vencido" continua escrito; só perde o vermelho de alarme.

Motivo: um aparelho aposentado com calibração vencida não é trabalho pendente, e pintá-lo de vermelho compete por atenção com os aparelhos que de fato precisam de ação. O texto fica para quem precisar do dado.

## Fora do escopo

- **Nenhuma migração** e nenhuma mudança de modelo: `ativo` já existe e já é lido pelas cinco regras de negócio (portal, dashboard, alertas e as duas cargas do GrowthHS). Nada disso é tocado.
- **O portal do cliente não muda.** Ele já filtra `ativo = true` no backend, então o cliente nunca viu aparelho inativo — não há o que indicar lá.
- **Filtro na aba do cliente** — descartado acima.
- **Nenhuma ação em massa** (ativar/desativar vários) — não foi pedido.

## Testes

**Backend** (`tests/test_frota_leitura.py`): com um aparelho ativo e um inativo no banco, `?ativo=true` devolve só o ativo, `?ativo=false` devolve só o inativo, e sem o parâmetro devolvem-se os dois (trava a compatibilidade). O filtro novo combina com o de calibração sem se atrapalharem.

**Frontend:** `app/frota/FrotaPage.test.tsx` **não existe hoje** — é criado por esta entrega. `app/clientes/ClienteEquipamentosTab.test.tsx` já existe e ganha casos novos. Cobrem: linha de aparelho inativo mostra o selo "Inativo" e a classe `opacity-60` no `<tr>`; linha de ativo não mostra nenhum dos dois; trocar o filtro "Aparelhos" dispara a chamada com o parâmetro correto e zera o `offset`; o badge de calibração de um inativo sai com tom neutro.

**Baseline:** esta máquina tem 4 falhas pré-existentes no backend e 1 no frontend. A falha do frontend é **`ClienteEquipamentosTab.test.tsx > esconde "Novo aparelho" para não-admin`** — exatamente um dos arquivos que esta entrega mexe. Ela já falhava antes e **não** é responsabilidade desta entrega; conferir o baseline antes de tratá-la como regressão.

## Arquivos

Backend: `app/api/equipamentos_cliente.py`, `tests/test_frota_leitura.py`. Frontend: `app/frota/api.ts` (o parâmetro no cliente HTTP), `app/frota/FrotaPage.tsx`, `app/clientes/ClienteEquipamentosTab.tsx` + testes ao lado. Changelog: entrada de release ao fechar.
