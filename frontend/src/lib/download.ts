/** Download de PDF deixando o usuário escolher a pasta, quando o navegador permite.
 *
 * O laboratório arquiva cada certificado numa pasta própria, e o `<a download>` de
 * sempre salva direto na pasta padrão sem perguntar. `showSaveFilePicker` abre a
 * janela nativa do sistema — e o Chrome LEMBRA a última pasta usada por site, então
 * da segunda vez em diante a janela já abre no lugar certo.
 */

/** Só o pedaço da File System Access API que usamos. Não está na lib DOM do TS. */
interface HandleGravavel {
  createWritable(): Promise<{ write(dado: Blob): Promise<void>; close(): Promise<void> }>
}
type AbrirJanelaSalvar = (opcoes: {
  suggestedName?: string
  types?: { description: string; accept: Record<string, string[]> }[]
}) => Promise<HandleGravavel>

function janelaSalvar(): AbrirJanelaSalvar | null {
  const w = window as unknown as { showSaveFilePicker?: AbrirJanelaSalvar }
  // Só existe em contexto seguro (https ou localhost) — em http nem aparece.
  return typeof w.showSaveFilePicker === 'function' ? w.showSaveFilePicker : null
}

/** Fallback histórico: link com `download`, que vai para a pasta padrão. */
function salvarDireto(blob: Blob, nome: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = nome
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

/** Devolve `true` se o usuário cancelou a janela — o chamador não deve tratar como erro. */
function cancelado(e: unknown): boolean {
  return e instanceof DOMException && e.name === 'AbortError'
}

/**
 * Abre a janela de "salvar como" e grava o PDF na pasta escolhida.
 *
 * `obterBlob` é uma FUNÇÃO, não um blob pronto, de propósito: a janela nativa exige
 * que o clique do usuário ainda esteja válido, e esse crédito expira em poucos
 * segundos. Como o PDF do certificado é renderizado por um Chromium no servidor e
 * pode demorar, buscar o arquivo ANTES de abrir a janela faria o navegador recusá-la.
 * Por isso: abre a janela primeiro, busca o PDF depois.
 *
 * Se o usuário cancelar, não faz nada e não lança. Em navegador sem a API (Firefox,
 * Safari) cai no download direto de sempre.
 */
export async function baixarPdfComEscolhaDePasta(
  nomeSugerido: string,
  obterBlob: () => Promise<Blob>,
): Promise<void> {
  const abrir = janelaSalvar()
  if (!abrir) {
    // Sem a janela, o `<a download>` já cria a entrada na barra de downloads do
    // navegador — de onde o usuário abre o PDF com um clique. Nada a acrescentar.
    salvarDireto(await obterBlob(), nomeSugerido)
    return
  }

  // A aba é reservada AGORA, ainda dentro do clique. Escolher a pasta leva tempo, e
  // abrir aba depois disso é barrado como pop-up — por isso ela nasce em branco aqui
  // e só recebe o PDF no fim. Se o usuário desistir, é fechada.
  const aba = window.open('', '_blank')

  let handle: HandleGravavel
  try {
    handle = await abrir({
      suggestedName: nomeSugerido,
      types: [{ description: 'PDF', accept: { 'application/pdf': ['.pdf'] } }],
    })
  } catch (e) {
    aba?.close()
    if (cancelado(e)) return
    // Qualquer outra recusa da janela (permissão, contexto inseguro) não pode
    // impedir o download: cai no caminho de sempre.
    salvarDireto(await obterBlob(), nomeSugerido)
    return
  }

  // A partir daqui o arquivo já existe no disco, vazio. Se a busca do PDF falhar,
  // sobra um arquivo de 0 byte — é o preço de abrir a janela antes de buscar, e o
  // erro chega ao usuário para ele tentar de novo.
  let blob: Blob
  try {
    blob = await obterBlob()
  } catch (e) {
    aba?.close()
    throw e
  }
  const escrita = await handle.createWritable()
  await escrita.write(blob)
  await escrita.close()

  // Salvar pela janela NÃO gera entrada na barra de downloads, que era de onde o
  // laboratório abria o PDF para imprimir. Reabrimos aqui para ele não precisar ir
  // até a pasta. (Abrir a PASTA é impossível: nenhum navegador expõe isso.)
  const url = URL.createObjectURL(blob)
  if (aba) aba.location.href = url
  else window.open(url, '_blank')
  // A aba ainda precisa da URL: revogar na hora deixaria a página em branco.
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}

const MIME_XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

/**
 * Salva uma planilha deixando o usuário escolher a pasta, quando o navegador permite.
 *
 * Mesma janela nativa do certificado, com duas diferenças de propósito:
 * - `obterBlob` continua sendo FUNÇÃO: a janela precisa abrir ainda dentro do clique,
 *   e a geração da planilha no servidor pode demorar mais que o crédito do clique.
 * - Não reabre o arquivo numa aba no fim. Isso existe no PDF porque o laboratório
 *   imprime o certificado logo depois; navegador nenhum renderiza xlsx, então aqui
 *   uma aba só mostraria tela em branco ou um segundo download.
 */
export async function baixarPlanilha(
  nomeSugerido: string,
  obterBlob: () => Promise<Blob>,
): Promise<void> {
  const abrir = janelaSalvar()
  if (!abrir) {
    salvarDireto(await obterBlob(), nomeSugerido)
    return
  }

  let handle: HandleGravavel
  try {
    handle = await abrir({
      suggestedName: nomeSugerido,
      types: [{ description: 'Planilha do Excel', accept: { [MIME_XLSX]: ['.xlsx'] } }],
    })
  } catch (e) {
    if (cancelado(e)) return
    salvarDireto(await obterBlob(), nomeSugerido)
    return
  }

  // A partir daqui o arquivo já existe no disco, vazio. Se a busca falhar sobra um
  // arquivo de 0 byte — é o preço de abrir a janela antes de buscar, e o erro sobe
  // para o botão mostrar ao usuário.
  const blob = await obterBlob()
  const escrita = await handle.createWritable()
  await escrita.write(blob)
  await escrita.close()
}
