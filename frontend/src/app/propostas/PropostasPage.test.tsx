import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ user: { id: 1, nome: 'Erick', email: 'e@hs.com', funcao_id: 1, funcao: 'Administrador' } }),
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
  listar.mockResolvedValue({ items: [PROPOSTA], total: 1, page: 1, page_size: 25, total_pages: 1 })
  excluir.mockResolvedValue(undefined)
})

describe('PropostasPage', () => {
  it('renderiza a lista com linha e ações', async () => {
    render(<PropostasPage />)
    expect(await screen.findByText('#42')).toBeInTheDocument()
    expect(screen.getByText('Cliente Teste')).toBeInTheDocument()
    expect(screen.getByText('36.312.056/0005-52')).toBeInTheDocument()
    expect(screen.getByText('R$ 1.250,50')).toBeInTheDocument()
    expect(screen.getByText('PDF')).toBeInTheDocument()
    expect(screen.getByText('Editar')).toBeInTheDocument()
    expect(screen.getByText('Histórico')).toBeInTheDocument()
    expect(screen.getByText('Excluir')).toBeInTheDocument()
  })

  it('Excluir confirma e chama propostasApi.excluir', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(<PropostasPage />)
    await screen.findByText('#42')
    fireEvent.click(screen.getByText('Excluir'))
    await waitFor(() => expect(excluir).toHaveBeenCalledWith(10))
    confirmSpy.mockRestore()
  })
})
