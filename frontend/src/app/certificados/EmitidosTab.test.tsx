import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { EmitidosTab } from './EmitidosTab'

const props = vi.fn()

vi.mock('../../components/ui/BotaoExportar', () => ({
  BotaoExportar: (p: unknown) => {
    props(p)
    return <button>Exportar Excel</button>
  },
}))

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
})
