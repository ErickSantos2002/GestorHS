import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { baixarPdfComEscolhaDePasta, baixarPlanilha } from './download'

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

function abaFalsa() {
  return { close: vi.fn(), location: { href: '' } }
}

afterEach(() => { semJanela(); vi.restoreAllMocks() })

describe('baixarPdfComEscolhaDePasta', () => {
  it('grava na pasta escolhida quando o navegador tem a janela', async () => {
    const { handle, escrito, close } = handleFalso()
    const abrir = vi.fn().mockResolvedValue(handle)
    comJanela(abrir)
    vi.spyOn(window, 'open').mockReturnValue(abaFalsa() as unknown as Window)
    URL.createObjectURL = vi.fn().mockReturnValue('blob:x')
    URL.revokeObjectURL = vi.fn()

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
    vi.spyOn(window, 'open').mockReturnValue(abaFalsa() as unknown as Window)
    URL.createObjectURL = vi.fn().mockReturnValue('blob:x')
    URL.revokeObjectURL = vi.fn()

    await baixarPdfComEscolhaDePasta('x.pdf', async () => { ordem.push('busca'); return PDF })

    expect(ordem).toEqual(['janela', 'busca'])
  })

  it('cancelar a janela nao lanca, nao busca o PDF e fecha a aba reservada', async () => {
    const obterBlob = vi.fn()
    const aba = abaFalsa()
    vi.spyOn(window, 'open').mockReturnValue(aba as unknown as Window)
    comJanela(vi.fn().mockRejectedValue(new DOMException('cancelou', 'AbortError')))

    await expect(baixarPdfComEscolhaDePasta('x.pdf', obterBlob)).resolves.toBeUndefined()
    expect(obterBlob).not.toHaveBeenCalled()
    // sem isso o usuario fica com uma aba em branco toda vez que desiste
    expect(aba.close).toHaveBeenCalled()
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

  it('erro ao buscar o PDF sobe para o chamador e fecha a aba', async () => {
    const { handle } = handleFalso()
    const aba = abaFalsa()
    vi.spyOn(window, 'open').mockReturnValue(aba as unknown as Window)
    comJanela(vi.fn().mockResolvedValue(handle))
    await expect(
      baixarPdfComEscolhaDePasta('x.pdf', async () => { throw new Error('500') }),
    ).rejects.toThrow('500')
    expect(aba.close).toHaveBeenCalled()
  })

  it('abre o PDF salvo numa aba, porque a janela nao gera entrada em downloads', async () => {
    const { handle } = handleFalso()
    const aba = abaFalsa()
    const open = vi.spyOn(window, 'open').mockReturnValue(aba as unknown as Window)
    comJanela(vi.fn().mockResolvedValue(handle))
    URL.createObjectURL = vi.fn().mockReturnValue('blob:pdf-salvo')
    URL.revokeObjectURL = vi.fn()

    await baixarPdfComEscolhaDePasta('x.pdf', async () => PDF)

    expect(open).toHaveBeenCalledWith('', '_blank')
    expect(aba.location.href).toBe('blob:pdf-salvo')
    expect(aba.close).not.toHaveBeenCalled()
  })

  it('reserva a aba ANTES de abrir a janela de salvar', async () => {
    // Escolher a pasta demora; abrir aba depois disso e barrado como pop-up.
    const ordem: string[] = []
    const { handle } = handleFalso()
    vi.spyOn(window, 'open').mockImplementation(() => { ordem.push('aba'); return abaFalsa() as unknown as Window })
    comJanela(vi.fn().mockImplementation(async () => { ordem.push('janela'); return handle }))
    URL.createObjectURL = vi.fn().mockReturnValue('blob:x')
    URL.revokeObjectURL = vi.fn()

    await baixarPdfComEscolhaDePasta('x.pdf', async () => PDF)
    expect(ordem).toEqual(['aba', 'janela'])
  })
})

describe('baixarPlanilha', () => {
  beforeEach(() => {
    URL.createObjectURL = vi.fn(() => 'blob:fake')
    URL.revokeObjectURL = vi.fn()
  })

  afterEach(() => {
    delete (window as unknown as { showSaveFilePicker?: unknown }).showSaveFilePicker
    vi.restoreAllMocks()
  })

  it('sem showSaveFilePicker cai no download direto', async () => {
    const blob = new Blob(['x'])
    const clique = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    await baixarPlanilha('lista.xlsx', async () => blob)
    expect(clique).toHaveBeenCalled()
    expect(URL.createObjectURL).toHaveBeenCalledWith(blob)
  })

  it('com showSaveFilePicker grava pela janela nativa', async () => {
    const write = vi.fn(async () => {})
    const close = vi.fn(async () => {})
    const abrir = vi.fn(async () => ({ createWritable: async () => ({ write, close }) }))
    ;(window as unknown as { showSaveFilePicker: unknown }).showSaveFilePicker = abrir

    const blob = new Blob(['x'])
    await baixarPlanilha('lista.xlsx', async () => blob)

    expect(abrir).toHaveBeenCalledWith(
      expect.objectContaining({ suggestedName: 'lista.xlsx' }),
    )
    expect(write).toHaveBeenCalledWith(blob)
    expect(close).toHaveBeenCalled()
  })

  it('cancelar a janela nao lanca e nao busca o arquivo', async () => {
    const abrir = vi.fn(async () => {
      throw new DOMException('cancelado', 'AbortError')
    })
    ;(window as unknown as { showSaveFilePicker: unknown }).showSaveFilePicker = abrir
    const obterBlob = vi.fn(async () => new Blob(['x']))

    await expect(baixarPlanilha('lista.xlsx', obterBlob)).resolves.toBeUndefined()
    expect(obterBlob).not.toHaveBeenCalled()
  })

  it('erro ao buscar o arquivo propaga para o chamador mostrar', async () => {
    const abrir = vi.fn(async () => ({
      createWritable: async () => ({ write: async () => {}, close: async () => {} }),
    }))
    ;(window as unknown as { showSaveFilePicker: unknown }).showSaveFilePicker = abrir

    await expect(
      baixarPlanilha('lista.xlsx', async () => { throw new Error('500') }),
    ).rejects.toThrow('500')
  })
})
