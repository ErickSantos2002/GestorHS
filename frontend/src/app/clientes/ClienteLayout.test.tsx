import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

vi.mock('../../auth/AuthContext', () => ({ useAuth: () => ({ user: { funcao: 'Administrador' } }) }))

const { obter, atualizar } = vi.hoisted(() => ({ obter: vi.fn(), atualizar: vi.fn() }))
vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return { ...real, clientesApi: { ...real.clientesApi, obter, atualizar } }
})
vi.mock('../cadastros/api', () => ({ gruposApi: { listar: () => Promise.resolve([]) } }))
vi.mock('./FuncionariosSection', () => ({ FuncionariosSection: () => <div>funcionarios</div> }))
vi.mock('./UsuariosPortalSection', () => ({ UsuariosPortalSection: () => <div>portal</div> }))
const { listar } = vi.hoisted(() => ({ listar: vi.fn().mockResolvedValue({ items: [], total: 0 }) }))
vi.mock('../frota/api', async (orig) => {
  const real = await orig<typeof import('../frota/api')>()
  return { ...real, equipamentosClienteApi: { listar } }
})

import { ClienteLayout } from './ClienteLayout'
import { ClienteDadosTab } from './ClienteDadosTab'
import { ClienteEquipamentosTab } from './ClienteEquipamentosTab'

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/app/clientes/:id" element={<ClienteLayout />}>
          <Route index element={<ClienteDadosTab />} />
          <Route path="equipamentos" element={<ClienteEquipamentosTab />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('ClienteLayout (abas por URL)', () => {
  beforeEach(() => {
    obter.mockResolvedValue({ id: 5, nome: 'ACME', ativo: true })
  })

  it('na raiz mostra a aba Dados (form do cliente)', async () => {
    renderAt('/app/clientes/5')
    expect(await screen.findByText('ACME')).toBeInTheDocument()
    expect(await screen.findByText('Salvar alterações')).toBeInTheDocument()
  })

  it('em /equipamentos mostra a lista, não o form', async () => {
    renderAt('/app/clientes/5/equipamentos')
    expect(await screen.findByText(/Nenhum aparelho/i)).toBeInTheDocument()
    expect(screen.queryByText('Salvar alterações')).toBeNull()
  })
})
