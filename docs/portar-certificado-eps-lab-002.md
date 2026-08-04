# Portar um certificado para o formato EPS-LAB-002

Passo a passo para atualizar o modelo de certificado de um aparelho ao formato novo (5 medições, erro, incerteza expandida, seções 7 e 8 vindas da Configuração, notas, QR dos auxiliares).

**Referência pronta:** `Iblow10 PRO` (equipamento 48). Abra o Código-fonte dele em Certificados › Modelos e use como fonte dos blocos.

---

## ⚠️ Antes de tudo: o que NUNCA se copia

O certificado de cada aparelho tem **cinco campos que são a identidade dele**. Copiar o HTML da referência inteiro por cima rotula o certificado com o documento errado — não conformidade direta.

| Campo | Onde fica | Exemplo iBlow10 PRO | Exemplo Mercury |
|---|---|---|---|
| Código do documento | cabeçalho, **nas duas páginas** | `EPS-LAB-002` | `EPS-LAB-003` |
| Título | cabeçalho, **nas duas páginas** | `Certificado de Calibração Iblow` | `Certificado de Calibração Mercury` |
| Método | seção 5 | `FLX-LAB-001` | `FLX-LAB-003` |
| Marca | seção 2 | `Sentech` | `Alcovisor` |
| Modelo | seção 2 | `iBlow10 PRO` | `Mercury` |

**Anote os cinco valores do aparelho ANTES de mexer** e confira depois. O código do documento e o título aparecem **duas vezes** cada (cabeçalho da página 1 e da página 2) — é o erro mais fácil de cometer, porque a segunda passa despercebida.

---

## A lista — 11 enxertos

Todos são **acréscimos ou trocas pontuais**. Nenhum apaga conteúdo existente, exceto o item 10.

### Cabeçalho

- [ ] **1. Imagem da ISO 27001** ao lado da ISO 9001. Colar logo depois da tag `<img>` da 9001:
  ```html
  <img align="right" alt="ISO 27001" height="75" src="https://gestorhsapi.healthsafetytech.com/certificado-imagens/arquivo/aa946bace5574a58.jpg" style="margin-right:5px" width="75" />
  ```
  A ordem importa: as duas flutuam à direita, então a que vem **depois** no código aparece **à esquerda**. O `margin-right:5px` é o vão entre elas.

### Seção 7 — Equipamentos auxiliares

- [ ] **2.** Trocar todo o texto do TESTO 622 por `[equipamentosauxiliares]`.
  Passa a vir de Certificados › Configurações — quando o termo-higrômetro for recalibrado, muda num lugar só em vez de em todos os modelos.

### Seção 8 — Padrões utilizados

- [ ] **3.** Trocar os valores fixos pelos tokens, preservando o texto ao redor:
  ```
  Etanol em Nitrogênio - Certificado: [padraocertificado] - Número do cilíndro: [padraocilindro] – Concentração de Etanol = ([padraoconcentracao] ± [padraoincerteza]) x 10⁻⁶ mol/mol.
  ```
  O `x 10⁻⁶ mol/mol` continua literal (é a unidade formatada em HTML com `<sup>`).

### Seção 9 — Resultados

- [ ] **4. Limites** → `[limitemin]mg/L` e `[limitemax]mg/L` no lugar de `0,15mg/L` / `0,19mg/L`.
- [ ] **5. Testes 4 e 5, e SAI a coluna Média** — a tabela fica com **5 colunas**: `Teste 1` a `Teste 5`.
  A Qualidade pediu (04/08/2026) para tirar a média do certificado impresso. **Ela continua no sistema**: o modal segue calculando e gravando `calib_teste_media`, e o valor continua espelhado na frota — só não vai mais para o papel. O token `[calibtestemedia]` continua existindo para quem precisar.
- [ ] **6. Linha "Erro de medição"** — cabeçalho com `colspan="5"` e a linha de valores `[erro1]`..`[erro5]`.
  ⚠️ Se você partir de um modelo que ainda tem a Média, são **quatro** edições ligadas: tirar o cabeçalho `Média`, tirar a célula `[calibtestemedia]`, baixar o `colspan` de 6 para 5 e tirar a célula `&nbsp;` do fim da linha de erros. Esquecer o `colspan` desalinha a tabela inteira.
- [ ] **7. Tabela da Incerteza Expandida**, logo abaixo da tabela de testes:
  ```
  Incerteza Expandida (U) | [incertezaexpandida] mg/L
  k = [fatork] (95% de confiança)
  ```

### Rodapé da página 2

- [ ] **8. Bloco NOTAS E INFORMAÇÕES PERTINENTES** (as 5 notas metrológicas), depois de `Situação : APROVADO`.
  Copiar da referência — é texto idêntico em todos os aparelhos.
  ⚠️ Precisa ficar **fora** do `<strong>` de "Situação : APROVADO", senão sai tudo em negrito.
- [ ] **9. `[qrcertificados]`** — os três QR dos certificados auxiliares.
- [ ] **10. Assinatura por último** — a ordem final é: notas → QR → assinatura (imagem + `FIEMS / SENAI - Metrologia`).
  Este é o único item que **move** conteúdo em vez de acrescentar.
- [ ] **11. Reduzir os espaçadores `<br />`** que empurravam a assinatura para o rodapé.
  Na referência sobraram 57 antes da assinatura; um modelo antigo costuma ter ~80. Sem cortar, o certificado estoura para uma terceira página.

---

## Conferência obrigatória depois de cada aparelho

- [ ] **Gerar o PDF e contar as páginas — tem que continuar em 2.** Uma folha a mais em todo certificado é o oposto do que a funcionalidade quer (parar de imprimir os três documentos auxiliares).
- [ ] **Conferir os 5 campos de identidade** da tabela do topo, incluindo as **duas ocorrências** do código e do título.
- [ ] **Olhar as notas** — se saírem em negrito, o bloco ficou dentro do `<strong>` (item 8).
- [ ] **Conferir se apareceram os 3 QR** com os rótulos por cima.
- [ ] **Conferir que a tabela de testes tem 5 colunas alinhadas** e que a faixa "Erro de medição" atravessa a largura toda — se o `colspan` ficou em 6, a tabela sai torta (item 6).

---

## Continua fixo no HTML, por decisão de 03/08/2026

Não são parte da portabilidade, mas vale saber que estão lá e não vêm da Configuração:

- `Dry Gás PPM : 100 µmol/mol` — existe o token `[drygasppm]` se um dia quiser
- `Técnico: Walbert Santos` — existe `[tecnico]`
- `Situação : APROVADO` — imprime aprovado **independente do resultado**; existe `[situcalib]`, que é o que o laboratório escolhe no modal

---

## Sobre o código do método

A planilha `docs/Certificado Iblow.xlsx`, que originou este formato, escreve `FLX-LAB-002` no método — mas o **template está correto**: o iBlow10 PRO é `FLX-LAB-001` (confirmado pelo Erick em 04/08/2026). A planilha é a especificação do **conteúdo**, não a fonte do código do método; cada aparelho tem o seu, e ele vem do template existente.

Ou seja: ao portar, **mantenha o código do método que já está no modelo do aparelho** e não copie o da referência.
