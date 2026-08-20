import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

const { enviarNotaFiscalCaixa } = vi.hoisted(() => ({ enviarNotaFiscalCaixa: vi.fn() }))
vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return { ...real, caixasApi: { ...real.caixasApi, enviarNotaFiscalCaixa } }
})

import { NotaFiscalCaixaModal } from './NotaFiscalCaixaModal'

const pdf = () => new File([new Uint8Array([1])], 'nf.pdf', { type: 'application/pdf' })
const xml = () => new File([new Uint8Array([2])], 'nf.xml', { type: 'application/xml' })

function preencher(campo: RegExp, arquivo: File) {
  fireEvent.change(screen.getByLabelText(campo), { target: { files: [arquivo] } })
}

describe('NotaFiscalCaixaModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    enviarNotaFiscalCaixa.mockResolvedValue({})
  })

  it('envia o PDF e o XML juntos', async () => {
    const onEnviado = vi.fn()
    render(<NotaFiscalCaixaModal caixaId={3} onClose={vi.fn()} onEnviado={onEnviado} />)

    fireEvent.change(screen.getByLabelText(/Número da nota fiscal/i), { target: { value: '12345' } })
    preencher(/PDF da nota/i, pdf())
    preencher(/XML da nota/i, xml())
    fireEvent.click(screen.getByText('Anexar'))

    await waitFor(() => expect(enviarNotaFiscalCaixa).toHaveBeenCalled())
    const [id, arquivoPdf, arquivoXml, numero] = enviarNotaFiscalCaixa.mock.calls[0]
    expect(id).toBe(3)
    expect(arquivoPdf.name).toBe('nf.pdf')
    expect(arquivoXml.name).toBe('nf.xml')
    expect(numero).toBe('12345')
    expect(onEnviado).toHaveBeenCalled()
  })

  it('so com o PDF nao envia — os dois sempre vao juntos', async () => {
    render(<NotaFiscalCaixaModal caixaId={3} onClose={vi.fn()} onEnviado={vi.fn()} />)
    fireEvent.change(screen.getByLabelText(/Número da nota fiscal/i), { target: { value: '1' } })
    preencher(/PDF da nota/i, pdf())
    fireEvent.click(screen.getByText('Anexar'))

    expect(await screen.findByText(/Escolha o XML/i)).toBeInTheDocument()
    expect(enviarNotaFiscalCaixa).not.toHaveBeenCalled()
  })

  it('so com o XML nao envia', async () => {
    render(<NotaFiscalCaixaModal caixaId={3} onClose={vi.fn()} onEnviado={vi.fn()} />)
    fireEvent.change(screen.getByLabelText(/Número da nota fiscal/i), { target: { value: '1' } })
    preencher(/XML da nota/i, xml())
    fireEvent.click(screen.getByText('Anexar'))

    expect(await screen.findByText(/Escolha o PDF/i)).toBeInTheDocument()
    expect(enviarNotaFiscalCaixa).not.toHaveBeenCalled()
  })
})
