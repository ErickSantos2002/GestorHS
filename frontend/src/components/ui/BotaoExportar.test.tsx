import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BotaoExportar } from './BotaoExportar'

const apiFetch = vi.fn()
const baixarPlanilha = vi.fn()

vi.mock('../../lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../lib/api')>()),
  apiFetch: (...args: unknown[]) => apiFetch(...args),
}))

vi.mock('../../lib/download', () => ({
  baixarPlanilha: (nome: string, obterBlob: () => Promise<Blob>) =>
    baixarPlanilha(nome, obterBlob),
}))

describe('BotaoExportar', () => {
  beforeEach(() => {
    apiFetch.mockReset()
    baixarPlanilha.mockReset()
    baixarPlanilha.mockImplementation(async (_nome, obterBlob) => { await obterBlob() })
    apiFetch.mockResolvedValue({ ok: true, blob: async () => new Blob(['x']) })
  })

  it('monta a query com os filtros preenchidos', async () => {
    render(<BotaoExportar caminho="/equipamentos-cliente/exportar"
                          params={{ status: 'vencido', cliente: 7 }} nome="equipamentos" />)
    fireEvent.click(screen.getByRole('button', { name: /exportar/i }))
    await waitFor(() => expect(apiFetch).toHaveBeenCalled())
    const url = apiFetch.mock.calls[0][0] as string
    expect(url).toContain('status=vencido')
    expect(url).toContain('cliente=7')
  })

  it('omite filtro vazio, nulo e indefinido da query', async () => {
    render(<BotaoExportar caminho="/clientes/exportar"
                          params={{ q: '', cliente: null, fase: undefined }} nome="clientes" />)
    fireEvent.click(screen.getByRole('button', { name: /exportar/i }))
    await waitFor(() => expect(apiFetch).toHaveBeenCalled())
    expect(apiFetch.mock.calls[0][0]).toBe('/clientes/exportar')
  })

  it('passa o nome sugerido do arquivo com a data', async () => {
    render(<BotaoExportar caminho="/clientes/exportar" params={{}} nome="clientes" />)
    fireEvent.click(screen.getByRole('button', { name: /exportar/i }))
    await waitFor(() => expect(baixarPlanilha).toHaveBeenCalled())
    expect(baixarPlanilha.mock.calls[0][0]).toMatch(/^clientes-\d{4}-\d{2}-\d{2}\.xlsx$/)
  })

  it('desabilita o botao enquanto gera', async () => {
    let liberar: (v: unknown) => void = () => {}
    apiFetch.mockReturnValue(new Promise((res) => { liberar = res }))
    render(<BotaoExportar caminho="/clientes/exportar" params={{}} nome="clientes" />)
    const botao = screen.getByRole('button', { name: /exportar/i })
    fireEvent.click(botao)
    await waitFor(() => expect(botao).toBeDisabled())
    liberar({ ok: true, blob: async () => new Blob(['x']) })
    await waitFor(() => expect(botao).not.toBeDisabled())
  })

  it('mostra a mensagem da api quando ela recusa', async () => {
    apiFetch.mockResolvedValue({
      ok: false, status: 400,
      json: async () => ({ detail: 'A exportacao ficou grande demais. Refine o filtro.' }),
    })
    render(<BotaoExportar caminho="/clientes/exportar" params={{}} nome="clientes" />)
    fireEvent.click(screen.getByRole('button', { name: /exportar/i }))
    expect(await screen.findByText(/grande demais/i)).toBeInTheDocument()
  })
})
