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
