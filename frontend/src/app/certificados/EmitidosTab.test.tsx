import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { EmitidosTab } from './EmitidosTab'

const props = vi.fn()

vi.mock('../../components/ui/BotaoExportar', () => ({
  BotaoExportar: (p: unknown) => {
    props(p)
    return <button>Exportar Excel</button>
  },
}))

const clientesListar = vi.fn()
vi.mock('../clientes/api', () => ({
  clientesApi: { listar: (...a: unknown[]) => clientesListar(...a) },
}))

const CLIENTE = { id: 7, nome: 'Acme Industria', cgc: '11222333000144', cpf: null, municipio: 'Recife', estado: 'PE', ativo: true }

describe('EmitidosTab', () => {
  it('leva o periodo digitado para a exportacao', () => {
    props.mockReset()
    render(<EmitidosTab />)
    fireEvent.change(screen.getByLabelText(/de/i), { target: { value: '2026-01-01' } })
    fireEvent.change(screen.getByLabelText(/at[eé]/i), { target: { value: '2026-06-30' } })
    const ultima = props.mock.calls.at(-1)![0] as { params: Record<string, unknown> }
    expect(ultima.params.de).toBe('2026-01-01')
    expect(ultima.params.ate).toBe('2026-06-30')
  })

  it('aponta para a rota de certificados emitidos', () => {
    props.mockReset()
    render(<EmitidosTab />)
    const primeira = props.mock.calls[0][0] as { caminho: string }
    expect(primeira.caminho).toBe('/certificados-emitidos/exportar')
  })

  it('avisa que a planilha sai sem previa na tela', () => {
    render(<EmitidosTab />)
    expect(screen.getByText(/planilha/i)).toBeInTheDocument()
  })

  it('leva o cliente escolhido para a exportacao', async () => {
    props.mockReset()
    clientesListar.mockReset()
    clientesListar.mockResolvedValue({ items: [CLIENTE], total: 1 })
    render(<EmitidosTab />)

    fireEvent.change(screen.getByLabelText(/cliente/i), { target: { value: 'Acme' } })
    await waitFor(() => expect(clientesListar).toHaveBeenCalledWith({ q: 'Acme', limit: 8 }))
    fireEvent.click(await screen.findByText('Acme Industria'))

    const ultima = props.mock.calls.at(-1)![0] as { params: Record<string, unknown> }
    expect(ultima.params.cliente).toBe(7)
  })

  it('sem cliente escolhido, nao manda a chave cliente', () => {
    props.mockReset()
    render(<EmitidosTab />)
    const ultima = props.mock.calls.at(-1)![0] as { params: Record<string, unknown> }
    expect(ultima.params.cliente).toBeUndefined()
  })

  it('permite limpar o cliente escolhido e voltar a exportar todos', async () => {
    props.mockReset()
    clientesListar.mockReset()
    clientesListar.mockResolvedValue({ items: [CLIENTE], total: 1 })
    render(<EmitidosTab />)

    fireEvent.change(screen.getByLabelText(/cliente/i), { target: { value: 'Acme' } })
    fireEvent.click(await screen.findByText('Acme Industria'))
    expect((props.mock.calls.at(-1)![0] as { params: Record<string, unknown> }).params.cliente).toBe(7)

    fireEvent.click(screen.getByText('trocar'))
    const ultima = props.mock.calls.at(-1)![0] as { params: Record<string, unknown> }
    expect(ultima.params.cliente).toBeUndefined()
  })
})
