import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

const { enviarNotasFiscaisCaixa } = vi.hoisted(() => ({ enviarNotasFiscaisCaixa: vi.fn() }))
vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return { ...real, caixasApi: { ...real.caixasApi, enviarNotasFiscaisCaixa } }
})

import { NotaFiscalCaixaModal } from './NotaFiscalCaixaModal'

function arquivo(nome: string, tipo: string) {
  return new File(['x'], nome, { type: tipo })
}

function preencherBloco(i: number, numero: string) {
  fireEvent.change(screen.getByLabelText(`Número da nota fiscal ${i + 1}`), { target: { value: numero } })
  fireEvent.change(screen.getByLabelText(`PDF da nota ${i + 1}`), {
    target: { files: [arquivo('a.pdf', 'application/pdf')] },
  })
  fireEvent.change(screen.getByLabelText(`XML da nota ${i + 1}`), {
    target: { files: [arquivo('a.xml', 'application/xml')] },
  })
}

// Como preencherBloco, mas com nomes de arquivo distinguiveis por bloco — para
// os testes que precisam provar que o arquivo certo fica com o numero certo
// (nao so que "algum" arquivo foi anexado).
function preencherBlocoDistinto(i: number, numero: string, letra: string) {
  fireEvent.change(screen.getByLabelText(`Número da nota fiscal ${i + 1}`), { target: { value: numero } })
  fireEvent.change(screen.getByLabelText(`PDF da nota ${i + 1}`), {
    target: { files: [arquivo(`${letra}.pdf`, 'application/pdf')] },
  })
  fireEvent.change(screen.getByLabelText(`XML da nota ${i + 1}`), {
    target: { files: [arquivo(`${letra}.xml`, 'application/xml')] },
  })
}

describe('NotaFiscalCaixaModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    enviarNotasFiscaisCaixa.mockResolvedValue({})
  })

  it('abre com um bloco so, e sem botao de remover', () => {
    render(<NotaFiscalCaixaModal caixaId={1} onClose={vi.fn()} onEnviado={vi.fn()} />)
    expect(screen.getByLabelText('Número da nota fiscal 1')).toBeInTheDocument()
    expect(screen.queryByLabelText('Número da nota fiscal 2')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /remover nota 1/i })).not.toBeInTheDocument()
  })

  it('o + acrescenta um bloco e o X tira', () => {
    render(<NotaFiscalCaixaModal caixaId={1} onClose={vi.fn()} onEnviado={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /adicionar nota/i }))
    expect(screen.getByLabelText('Número da nota fiscal 2')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /remover nota 2/i }))
    expect(screen.queryByLabelText('Número da nota fiscal 2')).not.toBeInTheDocument()
  })

  it('o erro diz QUAL bloco esta incompleto', async () => {
    render(<NotaFiscalCaixaModal caixaId={1} onClose={vi.fn()} onEnviado={vi.fn()} />)
    preencherBloco(0, '111')
    fireEvent.click(screen.getByRole('button', { name: /adicionar nota/i }))
    fireEvent.change(screen.getByLabelText('Número da nota fiscal 2'), { target: { value: '222' } })
    fireEvent.click(screen.getByRole('button', { name: 'Anexar' }))
    // Ancorado no inicio: "PDF da nota 2"/"XML da nota 2" (labels sempre visiveis)
    // tambem contem a substring "nota 2" e ambiguam um findByText solto.
    expect(await screen.findByText(/^nota 2:/i)).toBeInTheDocument()
    expect(enviarNotasFiscaisCaixa).not.toHaveBeenCalled()
  })

  it('com um bloco so o erro nao leva prefixo e comeca com maiuscula', async () => {
    render(<NotaFiscalCaixaModal caixaId={1} onClose={vi.fn()} onEnviado={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Anexar' }))
    expect(await screen.findByText('Informe o número da nota fiscal.')).toBeInTheDocument()
    expect(enviarNotasFiscaisCaixa).not.toHaveBeenCalled()
  })

  it('envia as duas notas numa chamada so', async () => {
    const onEnviado = vi.fn()
    render(<NotaFiscalCaixaModal caixaId={9} onClose={vi.fn()} onEnviado={onEnviado} />)
    preencherBloco(0, '111')
    fireEvent.click(screen.getByRole('button', { name: /adicionar nota/i }))
    preencherBloco(1, '222')
    fireEvent.click(screen.getByRole('button', { name: 'Anexar' }))
    await waitFor(() => expect(enviarNotasFiscaisCaixa).toHaveBeenCalledTimes(1))
    const [id, notas] = enviarNotasFiscaisCaixa.mock.calls[0]
    expect(id).toBe(9)
    expect(notas.map((n: { numero: string }) => n.numero)).toEqual(['111', '222'])
    expect(onEnviado).toHaveBeenCalled()
  })

  it('remover o bloco do meio nao troca os arquivos dos que sobram', async () => {
    render(<NotaFiscalCaixaModal caixaId={9} onClose={vi.fn()} onEnviado={vi.fn()} />)
    // Tres blocos, arquivos distinguiveis: A, B, C.
    preencherBlocoDistinto(0, '111', 'a')
    fireEvent.click(screen.getByRole('button', { name: /adicionar nota/i }))
    preencherBlocoDistinto(1, '222', 'b')
    fireEvent.click(screen.getByRole('button', { name: /adicionar nota/i }))
    preencherBlocoDistinto(2, '333', 'c')

    // Remove o do meio (nota 2 = bloco B).
    fireEvent.click(screen.getByRole('button', { name: /remover nota 2/i }))

    fireEvent.click(screen.getByRole('button', { name: 'Anexar' }))
    await waitFor(() => expect(enviarNotasFiscaisCaixa).toHaveBeenCalledTimes(1))
    const [, notas] = enviarNotasFiscaisCaixa.mock.calls[0] as [number, { numero: string; pdf: File; xml: File }[]]

    expect(notas).toHaveLength(2)
    expect(notas[0].numero).toBe('111')
    expect(notas[0].pdf.name).toBe('a.pdf')
    expect(notas[0].xml.name).toBe('a.xml')
    expect(notas[1].numero).toBe('333')
    expect(notas[1].pdf.name).toBe('c.pdf')
    expect(notas[1].xml.name).toBe('c.xml')
  })
})
