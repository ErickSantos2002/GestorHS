# Adoção dos cards manuais de Phoebus no TaskHS

**Data do levantamento:** 18/09/2026
**Executa:** Erick, no Konsole, contra o banco `taskhs`
**Pré-requisito:** o GestorHS com o critério estreito de espelhamento (`caixa_so_de_modulo`) já **deployado**

## Por que

Até 18/09/2026 o GestorHS não espelhava caixa com Phoebus, e o setor de Serviços criava esses cards à mão — eles têm `external_source` nulo. Com o critério estreito no ar, o GestorHS passa a espelhar essas caixas: sem adotar os cards manuais, o upsert **cria um segundo card** para a mesma caixa, e o board passa a mostrar `CX 1049` duas vezes. Foi o estrago dos 28 cards órfãos de jul–set/2026.

Adotar é gravar `external_source = 'gestorhs'` e `external_id = <id da caixa>` no card que já existe. O upsert então **encontra** esse card e o atualiza, em vez de criar outro.

⚠️ **`CardUpdate` da API do TaskHS não expõe `external_id`/`external_source`** — por isso é SQL, e não chamada de API.

## Os 8 cards (grupo A)

Todos na lista **202** (`🔬LIBERADOS DO LABORATÓRIO`), com a caixa na fase 6. **A 202 é exatamente a lista que o GestorHS usa para a fase 6**, então adotar não move card nenhum de lugar, não apaga histórico e não apaga comentário.

| card | caixa | cliente |
|---|---|---|
| 1935 | 1003 | ACTECH ALUMINA CHEMICAL TECHNOLOGY LTDA |
| 1964 | 1011 | CONSTRUTORA APIA S/A. |
| 1982 | 1028 | GERDAU AÇOS LONGOS S.A. |
| 1984 | 1030 | CONCESSIONARIA DAS LINHAS 5 E 17 DO METRO DE SAO PAULO S.A. |
| 2010 | 1041 | DIANA BIOENERGIA AVANHANDAVA SA (caixa mista) |
| 2012 | 1043 | VOTORANTIM CIMENTOS S/A |
| 2016 | 1047 | JF PASQUA CONDUTORES ELETRICOS EIRELI |
| 2018 | 1049 | CONSORCIO SAO BERNARDO AMBIENTAL |

## Os 4 que NÃO se adota (grupo B)

`639`, `670`, `685` e `692`. O GestorHS diz que essas caixas estão na fase 4 (Recebido) e o TaskHS tem os cards em `Serviços 🪛` / `Pendências`. Adotar arrastaria o card para a lista 196 (Expedição) no próximo espelhamento, desfazendo o trabalho de quem move o card.

⚠️ **Risco em aberto:** com o critério estreito no ar, o próximo avanço dessas 4 caixas cria um card novo na 196, ao lado do card manual. Resolver isso é decidir qual dos dois sistemas está certo, caixa por caixa — conversa própria, ainda não tida.

## Passo 1 — reconferir antes de gravar

```sql
select c.id card, c.title, c.list_id, c.archived,
       c.external_source, c.external_id
  from cards c
 where c.id in (1935,1964,1982,1984,2010,2012,2016,2018)
 order by c.id;
```

Confirme, para as 8 linhas: `external_source` **nulo**, `archived` **false**, `list_id` **202**. Se alguma divergir, pare e reavalie — o levantamento envelheceu.

E no banco `gestorhs`, confirme que as 8 caixas seguem na fase 6:

```sql
select id, fase from caixas
 where id in (1003,1011,1028,1030,1041,1043,1047,1049) order by id;
```

## Passo 2 — gravar

```sql
-- Adota os 8 cards manuais das caixas de Phoebus paradas no Pos-Vendas.
-- Os cards NAO saem de lugar: a lista 202 ja e' a que o GestorHS usa para a fase 6.
BEGIN;
UPDATE cards SET external_source = 'gestorhs', external_id = '1003' WHERE id = 1935;
UPDATE cards SET external_source = 'gestorhs', external_id = '1011' WHERE id = 1964;
UPDATE cards SET external_source = 'gestorhs', external_id = '1028' WHERE id = 1982;
UPDATE cards SET external_source = 'gestorhs', external_id = '1030' WHERE id = 1984;
UPDATE cards SET external_source = 'gestorhs', external_id = '1041' WHERE id = 2010;
UPDATE cards SET external_source = 'gestorhs', external_id = '1043' WHERE id = 2012;
UPDATE cards SET external_source = 'gestorhs', external_id = '1047' WHERE id = 2016;
UPDATE cards SET external_source = 'gestorhs', external_id = '1049' WHERE id = 2018;
COMMIT;
```

⚠️ **`uq_card_external` é `UniqueConstraint("external_source", "external_id")`.** Se alguma dessas caixas já tiver card espelhado — não deveria, o gate bloqueou desde sempre — o `UPDATE` viola a constraint. O `BEGIN`/`COMMIT` existe para abortar o lote inteiro nesse caso, em vez de deixar metade adotada.

## Passo 3 — conferir

Repita a consulta do Passo 1. As 8 linhas devem ter `external_source = 'gestorhs'` e o `external_id` da tabela acima, **com `list_id` ainda 202**.

## Rollback

```sql
BEGIN;
UPDATE cards SET external_source = NULL, external_id = NULL
 WHERE id in (1935,1964,1982,1984,2010,2012,2016,2018);
COMMIT;
```

Devolve os cards ao estado manual. Não desfaz card que o GestorHS tenha criado depois — para esses, arquive pela tela.
