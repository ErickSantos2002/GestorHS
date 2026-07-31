import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

let mockUser: { funcao: string | null } | null = { funcao: 'Administrador' }
vi.mock('../../auth/AuthContext', () => ({ useAuth: () => ({ user: mockUser }) }))

const { obter } = vi.hoisted(() => ({ obter: vi.fn() }))
vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return { ...real, equipamentosClienteApi: {
    obter,
    historico: () => Promise.resolve([]), ordens: () => Promise.resolve([]),
    certificados: () => Promise.resolve([]), transferencias: () => Promise.resolve([]),
  } }
})
vi.mock('../cadastros/api', () => ({ equipamentosApi: { listar: () => Promise.resolve([]) } }))

import { EquipamentoClienteDetailPage } from './EquipamentoClienteDetailPage'

const APARELHO = {
  id: 7, cliente: 5, cliente_nome: 'ACME', equipamento: 1, equipamento_descricao: 'Bafometro',
  modulo: 0, serie: 'S1', patrimonio: null, datacompra: null, ult_calibragem: null,
  prox_calibragem: null, ativo: true, status_calibracao: 'sem_data' as const, os_atual: null,
  calib_cert: null, calib_temp: null, calib_pressao: null, calib_teste1: null, calib_teste2: null,
  calib_teste3: null, calib_teste_media: null, calib_situacao: null,
  modulo_instalado: null, instalado_em: null, em_estoque: false,
}

function editar() {
  return render(
    <MemoryRouter initialEntries={['/app/equipamentos/7']}>
      <Routes>
        <Route path="/app/equipamentos/:id" element={<EquipamentoClienteDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

function criar() {
  return render(
    <MemoryRouter initialEntries={['/app/equipamentos/novo?cliente=5']}>
      <Routes>
        <Route path="/app/equipamentos/novo" element={<EquipamentoClienteDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

afterEach(() => { vi.clearAllMocks() })

describe('permissao do Comercial Pos-Vendas no formulario do aparelho', () => {
  it('em modo edicao, o formulario fica habilitado para Pos-Vendas', async () => {
    mockUser = { funcao: 'Comercial Pós-Vendas' }
    obter.mockResolvedValue(APARELHO)
    editar()
    const serie = await screen.findByLabelText('Série')
    expect(serie).not.toBeDisabled()
  })

  it('em modo criacao, o formulario fica desabilitado para Pos-Vendas', () => {
    mockUser = { funcao: 'Comercial Pós-Vendas' }
    criar()
    const serie = screen.getByLabelText('Série')
    expect(serie).toBeDisabled()
  })
})
