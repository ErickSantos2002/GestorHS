# Operação: Empresa no Tiny ERP

Entrega v1.54.0 (set/2026). Empresa criada ou editada no GestorHS vira contato no
Tiny (API v2, token). Nada volta do Tiny para cá.

## Ligar

1. Deploy + `alembic upgrade head` (`0031`: quatro colunas em `empresas`, aditiva).
2. Com `TINY_TOKEN` **vazio** nada acontece — dá para subir o código antes de ligar.
3. Pôr o `TINY_TOKEN` nas variáveis de ambiente do EasyPanel (o token sai do próprio
   Tiny, em Configurações > Token da API) e reiniciar.
4. `python -m app.scripts.enviar_empresas_tiny` (simula) → conferir → `--aplicar`.
   Em 16/09/2026 o esperado era: 9 adotadas, 1 criada.

## O que cada estado quer dizer

| Coluna "Tiny" | Significa |
|---|---|
| Enviada | Contato existe no Tiny e o id está guardado |
| Pendente | Na fila, ou o Tiny bloqueou por excesso de chamadas — o botão "Reenviar ao Tiny" resolve |
| Erro | O Tiny recusou; o motivo aparece ao passar o mouse |
| — | Integração desligada ou cadastro anterior a ela |

## Erros mais comuns

| Código | Mensagem típica | O que fazer |
|---|---|---|
| 31 | "Cidade não encontrada" | Corrigir o município na Empresa e reenviar. O Tiny casa pela tabela dele (aceita sem acento e completa a UF) |
| 30 | "Erro de Duplicidade de Registro" | O sistema já pesquisa e adota sozinho; se aparecer, reenviar resolve |
| 2 | "token inválido ou não encontrado" | Conferir o `TINY_TOKEN` no EasyPanel |
| 6 / 11 | "API bloqueada momentaneamente" | Esperar um minuto e reenviar. O limite desta conta é 20 chamadas/minuto (`x-limit-api`) |

## Coisas que não estão óbvias no código

- **A alteração do Tiny apaga o que não for enviado.** Por isso a integração lê o
  contato antes de alterar e devolve inteiro o que é de lá (código, tipos de contato,
  fantasia, pessoas de contato, e-mail de NFe). Nunca mande alteração parcial na mão.
- **`tipos_contato` acumula.** Só a criação manda `Cliente`; a edição devolve o que veio.
- **"Não encontrado" é o erro 20**, não uma lista vazia.
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
