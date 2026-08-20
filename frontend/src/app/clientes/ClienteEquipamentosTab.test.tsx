import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within, fireEvent } from '@testing-library/react'
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
    expect(listar).toHaveBeenCalledWith({ cliente: 5, offset: 0, limit: 25 })
  })

  it('mostra vazio quando não há aparelhos', async () => {
    listar.mockResolvedValue({ items: [], total: 0 })
    renderTab()
    expect(await screen.findByText(/Nenhum aparelho/i)).toBeInTheDocument()
  })

  it('mostra "Novo aparelho" para Expedição, que cadastra aparelho', async () => {
    mockUser = { funcao: 'Expedição' }
    listar.mockResolvedValue({ items: [], total: 0 })
    renderTab()
    await screen.findByText(/Nenhum aparelho/i)
    expect(screen.getByText('Novo aparelho')).toBeInTheDocument()
  })

  it('esconde "Novo aparelho" para quem nao gerencia cadastro', async () => {
    mockUser = { funcao: 'Financeiro' }
    listar.mockResolvedValue({ items: [], total: 0 })
    renderTab()
    await screen.findByText(/Nenhum aparelho/i)
    expect(screen.queryByText('Novo aparelho')).toBeNull()
  })

  it('esconde "Novo aparelho" para Pós-Vendas, que so edita', async () => {
    mockUser = { funcao: 'Comercial Pós-Vendas' }
    listar.mockResolvedValue({ items: [], total: 0 })
    renderTab()
    await screen.findByText(/Nenhum aparelho/i)
    expect(screen.queryByText('Novo aparelho')).toBeNull()
  })

  it('marca a linha do aparelho inativo com selo e esmaecido', async () => {
    listar.mockResolvedValue({ items: [
      { id: 1, cliente: 5, cliente_nome: 'ACME', equipamento: 9, equipamento_descricao: 'Bafômetro Novo',
        serie: 'SN-1', patrimonio: null, prox_calibragem: '2026-08-01', ativo: true, status_calibracao: 'em_dia' },
      { id: 2, cliente: 5, cliente_nome: 'ACME', equipamento: 9, equipamento_descricao: 'Bafômetro Velho',
        serie: 'SN-2', patrimonio: null, prox_calibragem: '2026-08-01', ativo: false, status_calibracao: 'vencido' },
    ], total: 2 })
    renderTab()

    const linhaInativa = (await screen.findByText('Bafômetro Velho')).closest('tr')
    expect(linhaInativa).not.toBeNull()
    expect(linhaInativa!.className).toContain('opacity-60')
    expect(within(linhaInativa!).getByText('Inativo')).toBeInTheDocument()

    const linhaAtiva = screen.getByText('Bafômetro Novo').closest('tr')
    expect(linhaAtiva!.className).not.toContain('opacity-60')
    expect(within(linhaAtiva!).queryByText('Inativo')).toBeNull()
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

describe('ClienteEquipamentosTab — paginacao', () => {
  beforeEach(() => {
    mockUser = { funcao: 'Administrador' }
    listar.mockReset()
  })

  const aparelho = (id: number, serie: string) => ({
    id, cliente: 5, cliente_nome: 'JSL S.A.', equipamento: 9, equipamento_descricao: 'Bafômetro X',
    serie, patrimonio: null, prox_calibragem: null, ativo: true, status_calibracao: 'em_dia',
  })

  it('pede a primeira pagina com limite explicito', async () => {
    listar.mockResolvedValue({ items: [aparelho(1, 'SN-1')], total: 1 })
    renderTab()
    await screen.findByText('SN-1')
    expect(listar).toHaveBeenCalledWith({ cliente: 5, offset: 0, limit: 25 })
  })

  it('cliente com mais aparelhos que a pagina mostra o total e navega ate o resto', async () => {
    // Caso real da JSL S.A. (cliente 1985): 27 aparelhos, e o F007214 era o 27o
    // — ficava fora dos 25 que a tela buscava, sem nenhum aviso de que faltava.
    const pagina1 = Array.from({ length: 25 }, (_, i) => aparelho(i + 1, `SN-${i + 1}`))
    listar.mockResolvedValue({ items: pagina1, total: 27 })
    renderTab()
    await screen.findByText('SN-1')

    // A contagem precisa deixar claro que existem 27, nao 25. Vem duas vezes:
    // a paginacao desenha a versao de desktop e a de mobile, uma escondida por CSS.
    expect(screen.getAllByText('27').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Mostrando/).length).toBeGreaterThan(0)

    listar.mockResolvedValue({ items: [aparelho(26, 'F'), aparelho(27, 'F007214')], total: 27 })
    fireEvent.click(screen.getByText('Próxima'))

    expect(await screen.findByText('F007214')).toBeInTheDocument()
    expect(listar).toHaveBeenLastCalledWith({ cliente: 5, offset: 25, limit: 25 })
  })

  it('cabendo tudo numa pagina, nao aparece navegacao', async () => {
    listar.mockResolvedValue({ items: [aparelho(1, 'SN-1')], total: 1 })
    renderTab()
    await screen.findByText('SN-1')
    expect(screen.queryByText('Próxima')).not.toBeInTheDocument()
  })
})
