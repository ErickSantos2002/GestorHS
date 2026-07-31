import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../../auth/AuthContext', () => ({ useAuth: () => ({ user: { funcao: 'Administrador' } }) }))

const { listar } = vi.hoisted(() => ({ listar: vi.fn() }))
vi.mock('./api', () => ({
  equipamentosClienteApi: { listar },
  STATUS_CALIBRACAO: {
    em_dia: { label: 'Em dia', tone: 'primary' as const },
    vencendo: { label: 'Vencendo', tone: 'warning' as const },
    vencido: { label: 'Vencido', tone: 'danger' as const },
    sem_data: { label: 'Sem data', tone: 'neutral' as const },
  },
}))

import { FrotaPage } from './FrotaPage'

function item(over: Partial<Record<string, unknown>> = {}) {
  return {
    id: 1, cliente: 5, cliente_nome: 'ACME', equipamento: 9,
    equipamento_descricao: 'Bafômetro X', serie: 'SN-1', patrimonio: null,
    prox_calibragem: '2026-08-01', ativo: true, status_calibracao: 'em_dia',
    ...over,
  }
}

function renderPage() {
  return render(<MemoryRouter initialEntries={['/app/equipamentos']}><FrotaPage /></MemoryRouter>)
}

describe('FrotaPage — aparelho inativo', () => {
  beforeEach(() => { listar.mockReset() })

  it('marca a linha do inativo com selo e esmaecido', async () => {
    listar.mockResolvedValue({ items: [
      item({ id: 1, equipamento_descricao: 'Bafômetro Novo', ativo: true }),
      item({ id: 2, equipamento_descricao: 'Bafômetro Velho', ativo: false, serie: 'SN-2' }),
    ], total: 2 })
    renderPage()

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
      item({ id: 3, equipamento_descricao: 'Vencido Inativo', ativo: false, status_calibracao: 'vencido' }),
    ], total: 1 })
    renderPage()
    // Escopo pela linha (via.closest('tr')): buscar 'Vencido' direto na tela e
    // ambíguo — a mesma palavra já existe como <option> do filtro "Status"
    // (renderizado de forma síncrona, antes do listar() assíncrono resolver),
    // e findByText resolvia contra essa opção sem esperar a linha da tabela.
    const linha = (await screen.findByText('Vencido Inativo')).closest('tr')
    const badge = within(linha!).getByText('Vencido')
    // tom neutral em vez de danger — o aparelho saiu de uso, nao e' fila de trabalho
    expect(badge.className).not.toContain('text-danger')
  })

  it('o filtro Aparelhos manda o parametro ativo na chamada', async () => {
    listar.mockResolvedValue({ items: [], total: 0 })
    renderPage()
    await screen.findByText(/Nenhum aparelho/i)
    expect(listar).toHaveBeenLastCalledWith(expect.objectContaining({ ativo: undefined }))

    await userEvent.selectOptions(screen.getByLabelText('Aparelhos'), 'true')
    expect(listar).toHaveBeenLastCalledWith(expect.objectContaining({ ativo: true }))

    await userEvent.selectOptions(screen.getByLabelText('Aparelhos'), 'false')
    expect(listar).toHaveBeenLastCalledWith(expect.objectContaining({ ativo: false }))

    await userEvent.selectOptions(screen.getByLabelText('Aparelhos'), '')
    expect(listar).toHaveBeenLastCalledWith(expect.objectContaining({ ativo: undefined }))
  })
})
