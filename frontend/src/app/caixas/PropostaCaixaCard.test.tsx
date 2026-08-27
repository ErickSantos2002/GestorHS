import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

let mockUser: { funcao: string } = { funcao: 'Financeiro' }
vi.mock('../../auth/AuthContext', () => ({ useAuth: () => ({ user: mockUser }) }))

const { proposta } = vi.hoisted(() => ({ proposta: vi.fn() }))
vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return { ...real, caixasApi: { ...real.caixasApi, proposta } }
})

const { faturar, desfaturar, baixarPdf } = vi.hoisted(() => ({
  faturar: vi.fn(), desfaturar: vi.fn(), baixarPdf: vi.fn(),
}))
vi.mock('../propostas/api', async (orig) => {
  const real = await orig<typeof import('../propostas/api')>()
  return { ...real, propostasApi: { ...real.propostasApi, faturar, desfaturar, baixarPdf } }
})

import { ApiError } from '../../lib/api'
import { PropostaCaixaCard } from './PropostaCaixaCard'

const PROPOSTA = {
  id: 42,
  numero: 189,
  data: '2026-08-20',
  cliente_nome: 'CONCREFER INDUSTRIA E COMERCIO',
  cliente_documento: '01899414000167',
  total: 790,
  faturada: false,
  faturada_em: null as string | null,
  faturada_por: null as string | null,
  is_deleted: false,
  deleted_at: null as string | null,
}

describe('PropostaCaixaCard', () => {
  beforeEach(() => {
    mockUser = { funcao: 'Financeiro' }
    vi.clearAllMocks()
    proposta.mockResolvedValue({ ...PROPOSTA })
  })

  it('mostra numero, data, cliente, CNPJ e valor', async () => {
    render(<PropostaCaixaCard caixaId={952} numeroProposta={189} />)

    expect(await screen.findByText('Proposta #189')).toBeTruthy()
    expect(screen.getByText('20/08/2026')).toBeTruthy()
    expect(screen.getByText('CONCREFER INDUSTRIA E COMERCIO')).toBeTruthy()
    expect(screen.getByText('01.899.414/0001-67')).toBeTruthy()
    expect(screen.getByText('R$ 790,00')).toBeTruthy()
  })

  it('nao busca nem desenha nada quando a caixa nao tem numero de proposta', () => {
    const { container } = render(<PropostaCaixaCard caixaId={952} numeroProposta={null} />)
    expect(proposta).not.toHaveBeenCalled()
    expect(container.firstChild).toBeNull()
  })

  it('nao desenha nada quando o numero e do CRM antigo (404)', async () => {
    proposta.mockRejectedValue(new ApiError(404, 'proposta não encontrada'))
    const { container } = render(<PropostaCaixaCard caixaId={952} numeroProposta={16511} />)

    await waitFor(() => expect(proposta).toHaveBeenCalled())
    await waitFor(() => expect(container.firstChild).toBeNull())
  })

  it('marca como faturada e passa a mostrar quem faturou', async () => {
    faturar.mockResolvedValue({ ...PROPOSTA, faturada: true, faturada_em: '2026-08-27T12:00:00Z', faturada_por: 'Fulano' })
    render(<PropostaCaixaCard caixaId={952} numeroProposta={189} />)

    fireEvent.click(await screen.findByText('Marcar como faturada'))

    await waitFor(() => expect(faturar).toHaveBeenCalledWith(42))
    expect(await screen.findByText('Faturada')).toBeTruthy()
    expect(screen.getByText(/Fulano/)).toBeTruthy()
    expect(screen.queryByText('Marcar como faturada')).toBeNull()
  })

  it('esconde o botao de faturar de quem nao e Financeiro nem Admin', async () => {
    mockUser = { funcao: 'Laboratório' }
    render(<PropostaCaixaCard caixaId={952} numeroProposta={189} />)

    await screen.findByText('Proposta #189')
    expect(screen.queryByText('Marcar como faturada')).toBeNull()
  })

  it('so o Admin ve o desfazer de uma proposta ja faturada', async () => {
    proposta.mockResolvedValue({ ...PROPOSTA, faturada: true, faturada_em: '2026-08-27T12:00:00Z', faturada_por: 'Fulano' })
    render(<PropostaCaixaCard caixaId={952} numeroProposta={189} />)
    await screen.findByText('Faturada')
    expect(screen.queryByText('Desfazer faturamento')).toBeNull()

    mockUser = { funcao: 'Administrador' }
    render(<PropostaCaixaCard caixaId={952} numeroProposta={189} />)
    expect(await screen.findByText('Desfazer faturamento')).toBeTruthy()
  })

  it('proposta desabilitada aparece marcada e sem o faturar', async () => {
    proposta.mockResolvedValue({ ...PROPOSTA, is_deleted: true, deleted_at: '2026-08-05T10:00:00Z' })
    render(<PropostaCaixaCard caixaId={952} numeroProposta={189} />)

    expect(await screen.findByText('Desabilitada')).toBeTruthy()
    expect(screen.queryByText('Marcar como faturada')).toBeNull()
    // Conferir o documento continua valendo — e' o que o Financeiro precisa ver.
    expect(screen.getByText('Visualizar')).toBeTruthy()
    expect(screen.getByText('Baixar')).toBeTruthy()
  })

  it('baixa o PDF pelo numero da proposta', async () => {
    baixarPdf.mockResolvedValue(new Blob([new Uint8Array([1])], { type: 'application/pdf' }))
    render(<PropostaCaixaCard caixaId={952} numeroProposta={189} />)

    fireEvent.click(await screen.findByText('Baixar'))
    await waitFor(() => expect(baixarPdf).toHaveBeenCalledWith(42))
  })

  it('abre a modal de visualizacao, que busca o PDF da proposta', async () => {
    baixarPdf.mockResolvedValue(new Blob([new Uint8Array([1])], { type: 'application/pdf' }))
    render(<PropostaCaixaCard caixaId={952} numeroProposta={189} />)

    fireEvent.click(await screen.findByText('Visualizar'))

    // A modal reusada de propostas busca o PDF ao montar — e a prova de que abriu.
    await waitFor(() => expect(baixarPdf).toHaveBeenCalledWith(42))
    expect(screen.getAllByText('Proposta #189').length).toBe(2)  // card + titulo da modal
  })
})
