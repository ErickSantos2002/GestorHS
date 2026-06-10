# GestorHS — Modal de certificado com todos os campos editáveis (override por OS)

**Data:** 2026-06-10
**Status:** Aprovado para implementação
**Motivação:** Muitos dados do certificado vêm automáticos do cliente/aparelho (nome, CNPJ, endereço, modelo, marca, série…). Alguns certificados específicos precisam de valores diferentes **sem alterar o cadastro** do cliente/aparelho. Solução: a modal de gerar/regerar mostra **todos** os campos, já pré-preenchidos com os valores automáticos; o laboratório altera só o que precisar naquele certificado.

**Contexto:** evolução da geração de certificados (v1.4.x). O motor `montar_contexto(db, ordem)` monta o contexto a partir de cliente/aparelho/calibração; `preencher` substitui os `[campos]`.

## Decisões (do usuário)
- Campos sobrescrevíveis: **Cliente** (Nome, CNPJ/CPF, Endereço) + **Aparelho** (Modelo, Marca, Série, Patrimônio, Data de compra). Calibração continua como hoje.
- Override fica salvo **só naquela OS** (persiste para regerações futuras); **nunca** altera o cadastro do cliente/aparelho.

## Modelo de dados
- Os valores de **calibração** seguem nas colunas existentes (`ordens.calib_*`, `data_calibracao`).
- As sobrescritas de **identidade** (8 campos abaixo) ficam numa nova coluna **`ordens.cert_overrides`** (JSON, nullable). Chaves = nomes dos placeholders do certificado:
  `nomecli`, `cnpj`, `endcli`, `modelo`, `marca`, `serie`, `patrimonio`, `datacompra`.

## Backend

### Migração (Alembic `0008_cert_overrides`)
- `ADD COLUMN ordens.cert_overrides JSON NULL` (usar `sa.JSON()` — funciona em Postgres e no SQLite dos testes). Reversível (`drop_column`). Aplicar no banco real **ao fim da execução** (padrão do projeto).
- Modelo `Ordem`: `cert_overrides = Column(JSON, nullable=True)` (import `JSON` de `sqlalchemy`). (Os testes criam tabelas a partir do modelo, então a coluna aparece automaticamente na suíte.)

### Motor (`app/core/certificado_gerar.py`)
- `montar_contexto`: depois de montar o contexto derivado, **sobrepor** os overrides salvos:
  ```python
  for chave, valor in (ordem.cert_overrides or {}).items():
      if valor:
          ctx[chave] = valor
  ```
  (apenas valores não-vazios sobrescrevem; vazio mantém o automático.)

### Schemas (`app/schemas/ordens.py`)
- `GerarCertificadoIn`: além dos campos atuais (`data_calibracao`, `calib_*`), adicionar os 8 de identidade (todos `str | None = None`): `nomecli`, `cnpj`, `endcli`, `modelo`, `marca`, `serie`, `patrimonio`, `datacompra`.
- Novo `CertificadoCamposOut` (valores efetivos para pré-preencher a modal):
  - identidade (str): `nomecli`, `cnpj`, `endcli`, `modelo`, `marca`, `serie`, `patrimonio`, `datacompra`
  - calibração: `calib_cert`, `calib_temp`, `calib_pressao`, `calib_teste1`, `calib_teste2`, `calib_teste3`, `calib_teste_media`, `calib_situacao` (str | None)
  - `data_calibracao: date | None`

### Endpoints (`app/api/certificados_os.py`)
- **`GET /ordens/{id}/certificado-campos`** (leitura, `get_current_usuario`; 404 se OS não existe): monta `ctx = montar_contexto(db, ordem)` (já com overrides sobrepostos) e devolve `CertificadoCamposOut` — identidade vinda do `ctx` (chaves de placeholder), calibração das colunas `ordem.calib_*`, `data_calibracao` de `ordem.data_calibracao` (como `date`). É a fonte de pré-preenchimento da modal.
- **`POST /ordens/{id}/gerar-certificado`** (Lab/Admin, como hoje): ao receber corpo —
  - grava `calib_*` (como hoje) e `data_calibracao` (como hoje: do form, com fallback);
  - monta `overrides = {k: getattr(dados, k) for k in _CAMPOS_OVERRIDE if getattr(dados, k)}` (8 chaves de identidade, só não-vazios) e grava `ordem.cert_overrides = overrides or None`;
  - `db.flush()`, depois `gerar_certificados(...)`, commit. **Não** espelha no aparelho.
  - Constante `_CAMPOS_OVERRIDE = ("nomecli","cnpj","endcli","modelo","marca","serie","patrimonio","datacompra")`.

## Frontend

### `app/ordens/api.ts`
- `GerarCertificadoPayload`: adicionar os 8 campos de identidade (`nomecli?`, `cnpj?`, `endcli?`, `modelo?`, `marca?`, `serie?`, `patrimonio?`, `datacompra?` — `string | null`).
- Novo tipo `CertificadoCampos` (mesma forma do `CertificadoCamposOut`) e método `ordensApi.certificadoCampos(id): Promise<CertificadoCampos>` → `GET /ordens/{id}/certificado-campos`.

### `GerarCertificadoModal.tsx` (reescrita do pré-preenchimento)
- Ao abrir: buscar `ordensApi.certificadoCampos(os.id)` e pré-preencher **todos** os campos a partir do resultado (em vez de ler só `os.calib_*`). Mostrar um spinner enquanto carrega.
- Layout em seções (usar o `Modal` com `size="lg"` se necessário para caber):
  - **Cliente:** Nome, CNPJ/CPF, Endereço.
  - **Aparelho:** Modelo, Marca, Série, Patrimônio, Data de compra (texto; pré-preenchido com o valor formatado).
  - **Calibração:** Data de calibração (date), Nº certificado, Situação (select), Temperatura, Pressão, Teste 1/2/3, Média (auto-cálculo mantido).
- Submeter: enviar identidade + calibração + data no payload de `gerarCertificado`. Manter `onGerado` recarregando a lista.
- Manter a lógica de média automática (calcMedia) já existente.

### `OrdemDetailPage.tsx`
- Sem mudança de gating (o botão Gerar/Regerar já existe). A modal agora carrega os campos do endpoint.

## Testes / verificação
- **Backend (pytest):**
  - `montar_contexto` aplica overrides (ex.: `cert_overrides={"nomecli":"OUTRO"}` → ctx["nomecli"]=="OUTRO"); sem override usa o derivado.
  - `GET certificado-campos` devolve os valores efetivos (derivado quando sem override; override quando há) + calibração das colunas; 404 se OS não existe.
  - `POST gerar-certificado` com campos de identidade grava `cert_overrides` (só não-vazios) e o HTML reflete os overrides; regerar sem mudar mantém overrides; cliente/aparelho **não** são alterados (ler o `Cliente` e conferir intacto).
- **Frontend (vitest/tsc/lint/build):** `certificadoCampos` monta a URL certa; payload inclui os campos de identidade; build verde.
- **E2E manual:** abrir gerar certificado → ver Cliente/Aparelho pré-preenchidos → alterar só o Nome → gerar → PDF sai com o nome alterado, e a ficha do cliente continua intacta → reabrir a modal e confirmar que o override foi mantido.

## Critérios de aceite
- A modal mostra todos os campos (Cliente, Aparelho, Calibração) pré-preenchidos com os valores automáticos.
- Alterar um campo e gerar reflete só naquele certificado; o cadastro do cliente/aparelho permanece intacto; o override persiste ao regerar.
- Não alterar nada e gerar produz o mesmo resultado de hoje.
- pytest/vitest/tsc/lint/build verdes; migração 0008 aplicada no banco real. Changelog v1.5.0.

## Fora do v1 desta etapa
Editar data de recebimento/próxima calibração/emissão na modal; sobrescrever campos por aparelho (em vez de por OS); histórico de versões do certificado.
