import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

vi.mock('../../auth/AuthContext', () => ({ useAuth: () => ({ user: { funcao: 'Administrador' } }) }))
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

function tela() {
  return render(
    <MemoryRouter initialEntries={['/app/clientes/5/equipamentos/9']}>
      <Routes>
        <Route path="/app/clientes/:id/equipamentos/:aparelho" element={<EquipamentoClienteDetailPage embutido />} />
        <Route path="/app/clientes/:id/equipamentos" element={<div>lista do cliente</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('EquipamentoClienteDetailPage (embutido)', () => {
  beforeEach(() => {
    obter.mockResolvedValue({ id: 9, cliente: 5, cliente_nome: 'ACME', equipamento: 1, equipamento_descricao: 'Bafômetro X',
      modulo: 0, serie: 'SN', patrimonio: null, datacompra: null, ult_calibragem: null, prox_calibragem: null,
      ativo: true, status: 'A', status_calibracao: 'em_dia', os_atual: null,
      calib_cert: null, calib_temp: null, calib_pressao: null, calib_teste1: null, calib_teste2: null, calib_teste3: null, calib_teste_media: null, calib_situacao: null })
  })

  it('carrega o aparelho da rota aninhada (params.aparelho)', async () => {
    tela()
    expect(await screen.findByText('Bafômetro X')).toBeInTheDocument()
    expect(obter).toHaveBeenCalledWith(9)
  })

  it('"Voltar" leva para a aba de equipamentos do cliente', async () => {
    const { getByText } = tela()
    await screen.findByText('Bafômetro X')
    fireEvent.click(getByText('Voltar'))
    expect(await screen.findByText('lista do cliente')).toBeInTheDocument()
  })
})
