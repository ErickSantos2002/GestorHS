# Operação: Empresa no Tiny ERP

Entrega v1.54.0 (set/2026). Empresa criada ou editada no GestorHS vira contato no
Tiny (API v2, token). Nada volta do Tiny para cá.

## Ligar

1. Deploy + `alembic upgrade head` (`0031`: quatro colunas em `empresas`, aditiva).
2. Com `TINY_TOKEN` **vazio** nada acontece — dá para subir o código antes de ligar.
3. Pôr o `TINY_TOKEN` nas variáveis de ambiente do EasyPanel (o token sai do próprio
   Tiny, em Configurações > Token da API) e reiniciar.
4. `python -m app.scripts.enviar_empresas_tiny` (simula) → conferir → `--aplicar`.
5. Pôr `JOB_TINY_ATIVO=true` para ligar o reenvio automático (ver abaixo) e reiniciar.

### Onde rodar o script

**No console do EasyPanel, dentro do container da API** — é lá que o `TINY_TOKEN`
está nas variáveis de ambiente e que o banco é o de produção de verdade.

⚠️ **Nunca rode o script da máquina de desenvolvimento.** O `backend/.env` de
desenvolvimento aponta para o **banco de produção**: rodar de lá grava em produção
por um caminho que ninguém está olhando, com o token que estiver na mão naquele
momento. E o Tiny **não tem ambiente de teste** — toda chamada cria contato de verdade.

A simulação (sem `--aplicar`) **faz a pesquisa de verdade** — é leitura pura, e é o
único jeito de saber quantos contatos seriam criados antes de valer. Ela nunca inclui
nem grava nada. O resumo traz `adotadas` / `criadas` / `puladas`.

### Critério de aceite da primeira rodada

O esperado em 16/09/2026 é **10 adotadas, 0 criadas**: as 9 filiais que já estavam no
Tiny mais a filial da Ibema (CNPJ `80228885001000`), criada à mão no teste de 16/09
(contato `610661344`).

**Qualquer "criada" nessa primeira rodada é sinal de problema** — provavelmente a
pesquisa não encontrou um contato que existe, e seguir criaria duplicado no ERP.
**Pare e avise** em vez de rodar de novo. `puladas` também pede olhada: é pesquisa que
não deu resposta clara (o script não cria nesse caso, de propósito).

## O que cada estado quer dizer

| Coluna "Tiny" | Significa |
|---|---|
| Enviada | Contato existe no Tiny e o id está guardado |
| Pendente | Na fila, ou a última tentativa falhou por algo transitório. O worker tenta de novo sozinho a cada 10 min; o botão "Reenviar ao Tiny" força na hora |
| Erro | O Tiny recusou; o motivo aparece ao passar o mouse |
| — | Integração desligada ou cadastro anterior a ela |

## Erros mais comuns

| Código | Mensagem típica | O que fazer |
|---|---|---|
| 31 | "Cidade não encontrada" | Corrigir o município na Empresa e reenviar. O Tiny casa pela tabela dele (aceita sem acento e completa a UF) |
| 30 | "Erro de Duplicidade de Registro" | O sistema já pesquisa e adota sozinho; se aparecer, reenviar resolve |
| 2 | "token inválido ou não encontrado" | Conferir o `TINY_TOKEN` no EasyPanel |
| 6 / 11 | "API bloqueada momentaneamente" | Esperar um minuto e reenviar. O limite desta conta é 20 chamadas/minuto (`x-limit-api`) |

## Reenvio automático das pendentes

`app/tarefas/tiny_pendentes.py` sobe junto com a API e varre a cada 10 minutos as
Empresas **ativas** em `pendente`, chamando o mesmo caminho do botão "Reenviar".
Sem nenhuma pendente, não fala com o Tiny. Ele existe porque `pendente` era um beco
sem saída: só alguém clicando no botão tirava a empresa de lá.

| Variável | Padrão | Para quê |
|---|---|---|
| `JOB_TINY_ATIVO` | `false` | Liga o worker. Nasce desligado: a máquina de desenvolvimento aponta para o banco de produção e o Tiny não tem ambiente de teste |
| `JOB_TINY_INTERVALO_MIN` | `10` | Minutos entre uma varredura e a seguinte |
| `JOB_TINY_LIMITE` | `20` | Teto de empresas por volta. Cada uma gasta 2 das 20 chamadas/minuto da conta |

Também não sobe sem `TINY_TOKEN`. No log: `job tiny: LIGADO, varredura a cada 10 min`
na subida, e uma linha por volta **só quando há pendência**.

Ele **não** pega `erro` (recusa que não muda sozinha — repetir gastaria chamada para
sempre) nem `tiny_status` nulo (cadastro anterior à integração, que é trabalho do
script de carga, conferido à mão de propósito).

## Coisas que não estão óbvias no código

- **A alteração do Tiny apaga o que não for enviado.** Por isso a integração lê o
  contato antes de alterar e devolve inteiro o que é de lá (código, tipos de contato,
  fantasia, pessoas de contato, e-mail de NFe). Nunca mande alteração parcial na mão.
- **`tipos_contato` acumula.** Só a criação manda `Cliente`; a edição devolve o que veio.
- **"Não encontrado" é o erro 20**, não uma lista vazia. E **só o erro 20 autoriza
  criar**: pesquisa que falhou de outro jeito (corpo não-JSON, 502, erro sem código)
  deixa em aberto se o contato já existe, então a empresa fica `pendente` e o script
  conta como `pulada`. Criar nesses casos duplicaria o contato no ERP.
- **A adoção confere o documento.** A pesquisa do Tiny casa por aproximação e a base
  tem várias filiais na mesma raiz de CNPJ (7 na raiz `05571228`): adotar o primeiro
  da lista grudaria a empresa no contato da vizinha, e dali em diante toda edição
  daqui sobrescreveria o cadastro dela.
- **A situação (ativo/inativo) é do Tiny.** A alteração devolve a situação que veio de
  lá; só a criação nasce `"A"`. Forçar `"A"` reativava quem tinha sido inativado no ERP.
- **Rede caída não é bloqueio do Tiny.** São coisas diferentes no log e na mensagem do
  script, mesmo que as duas deixem a empresa `pendente` para tentar de novo.
- **`ler_resposta` entende três formatos de resposta do Tiny**: `registros` (inclusão
  e alteração), `contatos` (pesquisa) e `contato` (obter) — cada endpoint devolve o
  contato numa chave diferente.
- **Com `tiny_id` mas sem conseguir ler o contato de novo e sem documento para
  pesquisar, o fluxo não recria o contato** — marca `pendente` e para ali. Criar às
  cegas geraria um segundo contato para a mesma empresa.
- **O Tiny não tem ambiente de teste:** qualquer ensaio com o token real cria contato
  de verdade. Os testes automatizados nunca chamam a API.
- **Nome acima de 50 caracteres é cortado no envio**; o cadastro daqui fica inteiro.
- **A pausa do script entre empresas é de 7 segundos**: cada empresa gasta duas
  chamadas e a conta permite 20 por minuto.
- Cliente (matriz) não vai para o Tiny; desativar e reativar não mexem lá.

## Clientes destinatários de proposta (set/2026)

Entrega v1.57.0. Todo Cliente que recebe proposta (`propostas.cliente`, com
`propostas.empresa` nulo) também vira contato no Tiny — mas aqui é **só criar ou
adotar**. Diferente da Empresa, **não existe caminho de alteração**: o cadastro de
Cliente vem do legado e tende a ser pior que o que já está no Tiny, então um contato
que já existe lá nunca é sobrescrito por aqui.

Criar, editar ou **duplicar** uma proposta para Cliente sem `tiny_id` marca
`clientes.tiny_status = 'pendente'` e agenda `sincronizar_cliente`; com `tiny_id`,
nenhuma chamada é feita. Cliente **inativo** entra do mesmo jeito — teve proposta,
então pode ser faturado (a *criação* de proposta nova continua recusando cliente
inativo; isso é só quem já tinha proposta). O worker de reenvio (`tiny_pendentes`)
passou a atender também `clientes.tiny_status = 'pendente'`, sempre **depois** das
Empresas e dividindo o mesmo `JOB_TINY_LIMITE`.

### Ligar (dos 212 clientes já com proposta)

1. **`alembic upgrade head` (`0032`: quatro colunas em `clientes`, aditiva, espelho
   da `0031`) ANTES do deploy** — rode a partir de um checkout desta branch (a imagem
   antiga ainda não tem o arquivo `0032`) com o `backend/.env` apontando para
   produção. O Dockerfile só sobe `uvicorn`, nunca roda `alembic` sozinho: fazer o
   deploy primeiro deixaria todo `SELECT` em `clientes` (e em `Empresa`, cujo
   `matriz_rel` é `lazy="joined"` e junta `clientes`) falhando entre a subida do
   container novo e a migração. A `0032` é aditiva, então aplicá-la antes é seguro —
   o código antigo não seleciona as colunas novas.
2. Deploy.
3. `python -m app.scripts.enviar_clientes_tiny` (simula) → conferir o resumo e o
   CSV em `relatorios/pendencias-clientes-tiny-<data>.csv`.
4. `python -m app.scripts.enviar_clientes_tiny --aplicar` — leva uns 25 min para os
   ~212 (7s de pausa por cliente, igual ao script de Empresas).
5. `JOB_TINY_ATIVO=true`, se ainda não estiver, para o worker reenviar os que
   ficaram `pendente`.

Mesmo aviso da Empresa vale aqui: **rodar só no console do EasyPanel**, nunca da
máquina de desenvolvimento — o `backend/.env` de lá aponta para o banco de produção
e o Tiny não tem ambiente de teste.

### O que fazer com cada motivo do CSV

| Motivo | O que fazer |
|---|---|
| Sem CNPJ/CPF | Corrigir o documento na página de Clientes e, se a proposta já foi salva sem ele, editar a proposta para o gatilho rodar de novo (ou esperar a próxima carga) |
| Documento pesquisado mas resposta inconclusiva ("pulada") | Conferir no Tiny à mão — o script não cria nesse caso de propósito, para não arriscar duplicar |
| Recusa do Tiny ("erro") | A mensagem é a que o próprio Tiny devolveu (ver a tabela de erros mais comuns acima) |

⚠️ **Pesquisa inconclusiva vira `pendente` que NUNCA se resolve sozinho.** Quando a
pesquisa não bate ("contato encontrado com documento diferente", corpo fora do
formato, etc.), o `sincronizar_cliente` (gatilho da proposta e worker) deixa o
cliente em `pendente` de propósito — criar ali arriscaria duplicar. A carga não:
ela só pula o cliente e o lista no CSV, sem mexer no status. Mas o worker de
`tiny_pendentes` repete a MESMA pesquisa a cada 10 min e recebe a MESMA resposta
inconclusiva: o cliente fica ocupando uma vaga do `JOB_TINY_LIMITE` (dividido com as
Empresas, que vêm primeiro) rodada após rodada, para sempre, sem sair do lugar. A
correção é manual: corrigir o documento do cliente ou o cadastro no Tiny e, se for o
caso, reenviar a proposta para o gatilho rodar de novo.

### Proposta cancelada não coloca o cliente na fila

`enviar_clientes_tiny.planejar()` só considera `propostas.is_deleted is False` —
proposta desfeita (cancelada) não é motivo para abrir contato no Tiny. Ao conferir
a fila por SQL, acrescente o mesmo filtro:

```sql
select tiny_status, count(*) from clientes
where id in (
  select cliente from propostas
  where empresa is null and cliente is not null and not is_deleted
)
group by 1;
```
