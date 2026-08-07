import { describe, it, expect, vi, afterEach } from 'vitest'
import { baixarPdfComEscolhaDePasta } from './download'

const PDF = new Blob(['%PDF-1.4'], { type: 'application/pdf' })

function comJanela(impl: unknown) {
  Object.defineProperty(window, 'showSaveFilePicker', { value: impl, configurable: true, writable: true })
}

function semJanela() {
  Reflect.deleteProperty(window as unknown as Record<string, unknown>, 'showSaveFilePicker')
}

function handleFalso() {
  const escrito: Blob[] = []
  const close = vi.fn().mockResolvedValue(undefined)
  return {
    escrito, close,
    handle: { createWritable: async () => ({ write: async (b: Blob) => { escrito.push(b) }, close }) },
  }
}

afterEach(() => { semJanela(); vi.restoreAllMocks() })

describe('baixarPdfComEscolhaDePasta', () => {
  it('grava na pasta escolhida quando o navegador tem a janela', async () => {
    const { handle, escrito, close } = handleFalso()
    const abrir = vi.fn().mockResolvedValue(handle)
    comJanela(abrir)

    await baixarPdfComEscolhaDePasta('certificado-1-calibracao.pdf', async () => PDF)

    expect(abrir).toHaveBeenCalledTimes(1)
    expect(abrir.mock.calls[0][0].suggestedName).toBe('certificado-1-calibracao.pdf')
    expect(escrito).toEqual([PDF])
    expect(close).toHaveBeenCalled()
  })

  it('abre a janela ANTES de buscar o PDF', async () => {
    // A janela nativa exige o clique do usuario ainda valido, e esse credito expira.
    // Buscar o PDF primeiro (o servidor renderiza com Chromium, demora) faria o
    // navegador recusar a janela — por isso a ordem e verificada explicitamente.
    const ordem: string[] = []
    const { handle } = handleFalso()
    comJanela(vi.fn().mockImplementation(async () => { ordem.push('janela'); return handle }))

    await baixarPdfComEscolhaDePasta('x.pdf', async () => { ordem.push('busca'); return PDF })

    expect(ordem).toEqual(['janela', 'busca'])
  })

  it('cancelar a janela nao lanca e nao busca o PDF', async () => {
    const obterBlob = vi.fn()
    comJanela(vi.fn().mockRejectedValue(new DOMException('cancelou', 'AbortError')))

    await expect(baixarPdfComEscolhaDePasta('x.pdf', obterBlob)).resolves.toBeUndefined()
    expect(obterBlob).not.toHaveBeenCalled()
  })

  it('sem a janela no navegador, baixa direto', async () => {
    semJanela()
    const click = vi.fn()
    vi.spyOn(document, 'createElement').mockReturnValue({
      click, remove: vi.fn(), set href(_v: string) {}, set download(_v: string) {},
    } as unknown as HTMLAnchorElement)
    vi.spyOn(document.body, 'appendChild').mockImplementation((n) => n)
    URL.createObjectURL = vi.fn().mockReturnValue('blob:x')
    URL.revokeObjectURL = vi.fn()

    await baixarPdfComEscolhaDePasta('x.pdf', async () => PDF)
    expect(click).toHaveBeenCalled()
  })

  it('erro ao buscar o PDF sobe para o chamador', async () => {
    const { handle } = handleFalso()
    comJanela(vi.fn().mockResolvedValue(handle))
    await expect(
      baixarPdfComEscolhaDePasta('x.pdf', async () => { throw new Error('500') }),
    ).rejects.toThrow('500')
  })
})
