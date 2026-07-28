import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

const useAuth = vi.fn()
vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => useAuth(),
}))

// Os modais são pesados (editor rico / fetch de versões) e não são o alvo aqui.
vi.mock('./PropostaModal', () => ({ PropostaModal: () => <div data-testid="proposta-modal" /> }))
vi.mock('./HistoricoModal', () => ({ HistoricoModal: () => <div data-testid="historico-modal" /> }))

const listar = vi.fn()
const excluir = vi.fn()
const duplicar = vi.fn()
const baixarPdf = vi.fn()

vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return {
    ...real,
    propostasApi: {
      ...real.propostasApi,
      listar: (...a: unknown[]) => listar(...a),
      excluir: (...a: unknown[]) => excluir(...a),
      duplicar: (...a: unknown[]) => duplicar(...a),
      baixarPdf: (...a: unknown[]) => baixarPdf(...a),
    },
  }
})

import { PropostasPage } from './PropostasPage'

const USUARIO_ADMIN = { id: 1, nome: 'Erick', email: 'e@hs.com', funcao_id: 1, funcao: 'Administrador' }
const USUARIO_SEM_ESCRITA = { id: 2, nome: 'Fulano', email: 'f@hs.com', funcao_id: 2, funcao: 'Laboratório' }

const PROPOSTA = {
  id: 10, numero: 42, data: '2026-07-20', cliente_nome: 'Cliente Teste', cliente_documento: '36312056000552',
  total: 1250.5, total_itens: 1250.5, desconto: 0, frete: 0, itens: [], aparelhos: [],
  cliente: 5, contato: null, vendedor: null, intro: null, outros_itens: null, forma_envio: null, forma_frete: null,
  transportador: null, condicao_pagamento: null, validade_dias: null, data_entrega: null, descricao_entrega: null,
  endereco_entrega_diferente: false, endereco_entrega: null, cliente_override: null, observacoes: null, assinatura: null,
  created_at: null, updated_at: null,
}

beforeEach(() => {
  vi.clearAllMocks()
  useAuth.mockReturnValue({ user: USUARIO_ADMIN })
  listar.mockResolvedValue({ items: [PROPOSTA], total: 1, page: 1, page_size: 25, total_pages: 1 })
  excluir.mockResolvedValue(undefined)
})

describe('PropostasPage', () => {
  it('renderiza a lista com linha e ações em ícone (usuário com escrita)', async () => {
    render(<PropostasPage />)
    expect(await screen.findByText('#42')).toBeInTheDocument()
    expect(screen.getByText('Cliente Teste')).toBeInTheDocument()
    expect(screen.getByText('36.312.056/0005-52')).toBeInTheDocument()
    expect(screen.getByText('R$ 1.250,50')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /visualizar/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /baixar pdf/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /histórico/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /editar/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /duplicar/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /excluir/i })).toBeInTheDocument()
  })

  it('esconde as ações de escrita para usuário sem permissão', async () => {
    useAuth.mockReturnValue({ user: USUARIO_SEM_ESCRITA })
    render(<PropostasPage />)
    await screen.findByText('#42')
    expect(screen.getByRole('button', { name: /visualizar/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /baixar pdf/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /histórico/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /editar/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /duplicar/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /excluir/i })).not.toBeInTheDocument()
  })

  it('Excluir confirma e chama propostasApi.excluir', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(<PropostasPage />)
    await screen.findByText('#42')
    fireEvent.click(screen.getByRole('button', { name: /excluir/i }))
    await waitFor(() => expect(excluir).toHaveBeenCalledWith(10))
    confirmSpy.mockRestore()
  })

  it('Visualizar abre o PDF numa aba nova sem baixar', async () => {
    baixarPdf.mockResolvedValue(new Blob(['conteudo']))
    const winStub = { location: { href: '' } } as unknown as Window
    const openSpy = vi.spyOn(window, 'open').mockReturnValue(winStub)
    // jsdom não implementa URL.createObjectURL — não há o que "spyOn" num
    // método inexistente, então atribuímos um stub diretamente e restauramos.
    const createObjectURLOriginal = URL.createObjectURL
    URL.createObjectURL = vi.fn().mockReturnValue('blob:mock-url')

    render(<PropostasPage />)
    await screen.findByText('#42')
    fireEvent.click(screen.getByRole('button', { name: /visualizar/i }))

    await waitFor(() => expect(baixarPdf).toHaveBeenCalledWith(10))
    expect(openSpy).toHaveBeenCalled()

    openSpy.mockRestore()
    URL.createObjectURL = createObjectURLOriginal
  })
})
