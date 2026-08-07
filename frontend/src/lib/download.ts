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
    salvarDireto(await obterBlob(), nomeSugerido)
    return
  }

  let handle: HandleGravavel
  try {
    handle = await abrir({
      suggestedName: nomeSugerido,
      types: [{ description: 'PDF', accept: { 'application/pdf': ['.pdf'] } }],
    })
  } catch (e) {
    if (cancelado(e)) return
    // Qualquer outra recusa da janela (permissão, contexto inseguro) não pode
    // impedir o download: cai no caminho de sempre.
    salvarDireto(await obterBlob(), nomeSugerido)
    return
  }

  // A partir daqui o arquivo já existe no disco, vazio. Se a busca do PDF falhar,
  // sobra um arquivo de 0 byte — é o preço de abrir a janela antes de buscar, e o
  // erro chega ao usuário para ele tentar de novo.
  const blob = await obterBlob()
  const escrita = await handle.createWritable()
  await escrita.write(blob)
  await escrita.close()
}
