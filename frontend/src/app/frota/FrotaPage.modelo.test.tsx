import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'

vi.mock('../../auth/AuthContext', () => ({ useAuth: () => ({ user: { funcao: 'Consulta' } }) }))

const { listar, resumoPorModelo, listarModelos } = vi.hoisted(() => ({
  listar: vi.fn(), resumoPorModelo: vi.fn(), listarModelos: vi.fn(),
}))
vi.mock('./api', () => ({
  equipamentosClienteApi: { listar, resumoPorModelo },
  STATUS_CALIBRACAO: {
    em_dia: { label: 'Em dia', tone: 'primary' as const },
    vencendo: { label: 'Vencendo', tone: 'warning' as const },
    vencido: { label: 'Vencido', tone: 'danger' as const },
    sem_data: { label: 'Sem data', tone: 'neutral' as const },
  },
}))
vi.mock('../cadastros/api', () => ({ equipamentosApi: { listar: listarModelos } }))

import { FrotaPage } from './FrotaPage'

function Local() {
  const l = useLocation()
  return <span data-testid="url">{l.pathname + l.search}</span>
}

function renderPage(url: string) {
  return render(<MemoryRouter initialEntries={[url]}><FrotaPage /><Local /></MemoryRouter>)
}

describe('FrotaPage — filtro por modelo', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listar.mockResolvedValue({ items: [], total: 0 })
    listarModelos.mockResolvedValue([
      { id: 47, descricao: 'Módulo' }, { id: 36, descricao: 'Phoebus' },
    ])
  })

  it('abre com ?equipamento= da URL aplicado', async () => {
    renderPage('/app/equipamentos?equipamento=36')
    await screen.findByText(/Nenhum aparelho/i)
    expect(listar).toHaveBeenLastCalledWith(expect.objectContaining({ equipamento: 36 }))
    await waitFor(() => expect((screen.getByLabelText('Modelo') as HTMLSelectElement).value).toBe('36'))
  })

  it('trocar o modelo grava na URL, preserva o cliente e zera a página', async () => {
    renderPage('/app/equipamentos?cliente=5')
    await screen.findByRole('option', { name: 'Phoebus' })
    await userEvent.selectOptions(screen.getByLabelText('Modelo'), '36')
    expect(listar).toHaveBeenLastCalledWith(expect.objectContaining({ equipamento: 36, cliente: 5, offset: 0 }))
    expect(screen.getByTestId('url').textContent).toContain('equipamento=36')
    expect(screen.getByTestId('url').textContent).toContain('cliente=5')
  })

  it('modelos em ordem alfabética', async () => {
    renderPage('/app/equipamentos')
    await screen.findByRole('option', { name: 'Phoebus' })
    const nomes = Array.from((screen.getByLabelText('Modelo') as HTMLSelectElement).options).map((o) => o.text)
    expect(nomes).toEqual(['Todos', 'Módulo', 'Phoebus'])
  })
})
