import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

let mockUser: { funcao: string | null } | null = { funcao: 'Administrador' }
vi.mock('../../auth/AuthContext', () => ({ useAuth: () => ({ user: mockUser }) }))

const { listar } = vi.hoisted(() => ({ listar: vi.fn() }))
vi.mock('../frota/api', () => ({
  equipamentosClienteApi: { listar },
  STATUS_CALIBRACAO: {
    em_dia: { label: 'Em dia', tone: 'primary' as const },
    vencendo: { label: 'Vencendo', tone: 'warning' as const },
    vencido: { label: 'Vencido', tone: 'danger' as const },
    sem_data: { label: 'Sem data', tone: 'neutral' as const },
  },
}))

import { ClienteEquipamentosTab } from './ClienteEquipamentosTab'

function renderTab() {
  return render(
    <MemoryRouter initialEntries={['/app/clientes/5/equipamentos']}>
      <Routes>
        <Route path="/app/clientes/:id/equipamentos" element={<ClienteEquipamentosTab />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ClienteEquipamentosTab', () => {
  beforeEach(() => {
    mockUser = { funcao: 'Administrador' }
    listar.mockReset()
  })

  it('lista os aparelhos do cliente', async () => {
    listar.mockResolvedValue({ items: [
      { id: 1, cliente: 5, cliente_nome: 'ACME', equipamento: 9, equipamento_descricao: 'Bafômetro X',
        serie: 'SN-1', patrimonio: null, prox_calibragem: '2026-08-01', ativo: true, status_calibracao: 'em_dia' },
    ], total: 1 })
    renderTab()
    expect(await screen.findByText('Bafômetro X')).toBeInTheDocument()
    expect(listar).toHaveBeenCalledWith({ cliente: 5 })
  })

  it('mostra vazio quando não há aparelhos', async () => {
    listar.mockResolvedValue({ items: [], total: 0 })
    renderTab()
    expect(await screen.findByText(/Nenhum aparelho/i)).toBeInTheDocument()
  })

  it('esconde "Novo aparelho" para não-admin', async () => {
    mockUser = { funcao: 'Expedição' }
    listar.mockResolvedValue({ items: [], total: 0 })
    renderTab()
    await screen.findByText(/Nenhum aparelho/i)
    expect(screen.queryByText('Novo aparelho')).toBeNull()
  })

  it('marca a linha do aparelho inativo com selo e esmaecido', async () => {
    listar.mockResolvedValue({ items: [
      { id: 1, cliente: 5, cliente_nome: 'ACME', equipamento: 9, equipamento_descricao: 'Bafômetro Ativo',
        serie: 'SN-1', patrimonio: null, prox_calibragem: '2026-08-01', ativo: true, status_calibracao: 'em_dia' },
      { id: 2, cliente: 5, cliente_nome: 'ACME', equipamento: 9, equipamento_descricao: 'Bafômetro Inativo',
        serie: 'SN-2', patrimonio: null, prox_calibragem: '2026-08-01', ativo: false, status_calibracao: 'vencido' },
    ], total: 2 })
    renderTab()

    const linhaInativa = (await screen.findByText('Bafômetro Inativo')).closest('tr')
    expect(linhaInativa).not.toBeNull()
    expect(linhaInativa!.className).toContain('opacity-60')
    expect(linhaInativa!.textContent).toContain('Inativo')

    const linhaAtiva = screen.getByText('Bafômetro Ativo').closest('tr')
    expect(linhaAtiva!.className).not.toContain('opacity-60')
    expect(linhaAtiva!.textContent).not.toContain('Inativo')
  })

  it('nao pinta de alarme a calibracao de um aparelho inativo', async () => {
    listar.mockResolvedValue({ items: [
      { id: 3, cliente: 5, cliente_nome: 'ACME', equipamento: 9, equipamento_descricao: 'Vencido Inativo',
        serie: 'SN-3', patrimonio: null, prox_calibragem: '2026-01-01', ativo: false, status_calibracao: 'vencido' },
    ], total: 1 })
    renderTab()
    const badge = await screen.findByText('Vencido')
    expect(badge.className).not.toContain('text-danger')
  })
})
