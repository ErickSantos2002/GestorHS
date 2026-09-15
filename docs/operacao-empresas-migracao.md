# Operação: Empresas e migração das propostas antigas

Entrega v1.53.0 (set/2026). A proposta passa a ter como destinatário um Cliente ou uma
Empresa (filial), e os dados editados no modal gravam no cadastro. Cada proposta guarda uma
cópia congelada (`propostas.destinatario`); `cliente_override` fica congelado.

## Ordem em produção

1. **Deploy** da branch já na `main`.
2. **Migração** `0030_empresas` (só DDL): `alembic upgrade head`. Cria `empresas` e as colunas
   `propostas.empresa` e `propostas.destinatario`. Não mexe em dado nenhum.
   Até o passo 4, proposta antiga sem cópia é exibida exatamente como antes (cadastro +
   override), então não há janela de PDF quebrado.
3. **Simular** a migração das propostas:
   `python -m app.scripts.migrar_filiais_propostas`
   Esperado na base de 15/09/2026: ~258 propostas a congelar, ~14 empresas a criar, 15
   propostas a ligar. Conferir a lista de **RECUSADOS** (documento que já é de um Cliente —
   decidir à mão se aquela proposta deveria apontar para o cliente) e de **INVALIDOS**
   (documento com dígito errado ou override sem nome — ficam só congeladas).
4. **Gravar**: `python -m app.scripts.migrar_filiais_propostas --aplicar`. Idempotente.

## Voltar a versão (downgrade)

`alembic downgrade 0029_notas_fiscais` apaga `empresas` e as duas colunas novas. Proposta
criada ou salva **depois** da 0030 não tem override: sem a cópia, o PDF dela volta a sair só
com o cadastro do cliente (e a de filial sai com os dados da matriz). Antes de voltar, liste
essas propostas (`updated_at` depois do deploy) e avise o comercial.

## Regras que não estão óbvias no código

- Documento é único **somando** clientes e empresas. Do lado do cadastro de Clientes a trava
  só olha Empresas: duplicata antiga entre clientes não pode travar edição.
- `unificar_clientes` reaponta `empresas.cliente` junto com as outras FKs de `clientes`.
- Telefone editado pela proposta grava em `clientes.telefones`; celular e WhatsApp não mudam.
- `clientes.numero` é inteiro: "S/N" digitado na proposta vira nulo no cliente (a Empresa
  guarda o texto).
- **`PUT /propostas/{id}` sem `destinatario` no corpo não mexe na cópia congelada** — ela só é
  (re)gravada quando o payload traz o bloco `destinatario` (o modal sempre manda). **Duplicar**
  proposta copia o destinatário atual do original (a cópia congelada, ou o resultado de
  `destinatario_legado` numa proposta antiga) para a nova, em vez de recongelar a partir do
  cadastro.
- Busca de destinatário que falha no modal mostra o erro e **não** oferece "Cadastrar
  empresa" — esse atalho só aparece quando a busca funciona e não encontra ninguém.
