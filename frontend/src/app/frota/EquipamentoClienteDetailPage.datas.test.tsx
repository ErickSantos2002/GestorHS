import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
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

function novo() {
  return render(
    <MemoryRouter initialEntries={['/app/equipamentos/novo?cliente=5']}>
      <Routes>
        <Route path="/app/equipamentos/novo" element={<EquipamentoClienteDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

function campo(label: string) {
  return screen.getByLabelText(label) as HTMLInputElement
}

describe('datas padrao do aparelho novo', () => {
  afterEach(() => vi.useRealTimers())

  it('preenche compra e ultima calibracao com hoje, e proxima com um ano depois', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 6, 20, 10, 0, 0)) // 20/07/2026, horario local
    novo()
    expect(campo('Compra').value).toBe('2026-07-20')
    expect(campo('Última calibração').value).toBe('2026-07-20')
    expect(campo('Próxima calibração').value).toBe('2027-07-20')
  })

  it('usa a data LOCAL, nao a UTC (a noite no Brasil viraria o dia seguinte)', () => {
    vi.useFakeTimers()
    // 22h no fuso local: toISOString() daria 2026-07-21 se o fuso for negativo
    vi.setSystemTime(new Date(2026, 6, 20, 22, 30, 0))
    novo()
    expect(campo('Compra').value).toBe('2026-07-20')
    expect(campo('Próxima calibração').value).toBe('2027-07-20')
  })

  it('nao inventa datas ao editar um aparelho existente', async () => {
    obter.mockResolvedValue({
      id: 9, cliente: 5, cliente_nome: 'ACME', equipamento: 1, equipamento_descricao: 'Bafômetro X',
      modulo: 0, serie: 'SN', patrimonio: null, datacompra: null, ult_calibragem: null, prox_calibragem: null,
      ativo: true, status: 'A', status_calibracao: 'em_dia', os_atual: null,
      calib_cert: null, calib_temp: null, calib_pressao: null, calib_teste1: null,
      calib_teste2: null, calib_teste3: null, calib_teste_media: null, calib_situacao: null,
    })
    render(
      <MemoryRouter initialEntries={['/app/equipamentos/9']}>
        <Routes><Route path="/app/equipamentos/:id" element={<EquipamentoClienteDetailPage />} /></Routes>
      </MemoryRouter>,
    )
    expect(await screen.findByText('Bafômetro X')).toBeInTheDocument()
    expect(campo('Compra').value).toBe('')
    expect(campo('Última calibração').value).toBe('')
  })
})
