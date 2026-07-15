import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

vi.mock('../../auth/AuthContext', () => ({ useAuth: () => ({ user: { funcao: 'Administrador' } }) }))

const { obterCliente } = vi.hoisted(() => ({ obterCliente: vi.fn() }))
vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return { ...real, clientesApi: { ...real.clientesApi, obter: obterCliente } }
})

const { obterAparelho } = vi.hoisted(() => ({ obterAparelho: vi.fn() }))
vi.mock('../frota/api', async (orig) => {
  const real = await orig<typeof import('../frota/api')>()
  return { ...real, equipamentosClienteApi: {
    obter: obterAparelho,
    historico: () => Promise.resolve([]), ordens: () => Promise.resolve([]),
    certificados: () => Promise.resolve([]), transferencias: () => Promise.resolve([]),
  } }
})
vi.mock('../cadastros/api', () => ({ equipamentosApi: { listar: () => Promise.resolve([]) } }))

import { ClienteLayout } from './ClienteLayout'
import { EquipamentoClienteDetailPage } from '../frota/EquipamentoClienteDetailPage'

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/app/clientes/:id" element={<ClienteLayout />}>
          <Route path="equipamentos/:aparelho" element={<EquipamentoClienteDetailPage embutido />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('detalhe do aparelho embutido no ClienteLayout (regressao chrome duplicado)', () => {
  beforeEach(() => {
    obterCliente.mockResolvedValue({ id: 5, nome: 'ACME', ativo: true })
    obterAparelho.mockResolvedValue({ id: 9, cliente: 5, cliente_nome: 'ACME', equipamento: 1, equipamento_descricao: 'Bafômetro X',
      modulo: 0, serie: 'SN', patrimonio: null, datacompra: null, ult_calibragem: null, prox_calibragem: null,
      ativo: true, status: 'A', status_calibracao: 'em_dia', os_atual: null,
      calib_cert: null, calib_temp: null, calib_pressao: null, calib_teste1: null, calib_teste2: null, calib_teste3: null, calib_teste_media: null, calib_situacao: null })
  })

  it('mostra so um Excluir, um Voltar, a breadcrumb e o nome do aparelho', async () => {
    renderAt('/app/clientes/5/equipamentos/9')
    expect(await screen.findByText('Bafômetro X')).toBeInTheDocument()
    expect(screen.getAllByText('ACME').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Excluir')).toHaveLength(1)
    expect(screen.getAllByText('Voltar')).toHaveLength(1)
    expect(screen.getByText((_content, el) => el?.tagName.toLowerCase() === 'p' && el.textContent === 'Equipamentos › Bafômetro X')).toBeInTheDocument()
  })
})
