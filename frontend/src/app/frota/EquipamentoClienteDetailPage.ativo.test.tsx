import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

vi.mock('../../auth/AuthContext', () => ({ useAuth: () => ({ user: { funcao: 'Administrador' } }) }))
const { obter, atualizar } = vi.hoisted(() => ({ obter: vi.fn(), atualizar: vi.fn() }))
vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return { ...real, equipamentosClienteApi: {
    obter, atualizar,
    historico: () => Promise.resolve([]), ordens: () => Promise.resolve([]),
    certificados: () => Promise.resolve([]), transferencias: () => Promise.resolve([]),
  } }
})
vi.mock('../cadastros/api', () => ({ equipamentosApi: { listar: () => Promise.resolve([{ id: 1, descricao: 'Bafometro' }]) } }))

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

afterEach(() => { vi.clearAllMocks() })

describe('controle unico de ativo', () => {
  it('nao renderiza mais o select de Situacao', async () => {
    obter.mockResolvedValue(APARELHO)
    editar()
    expect(await screen.findByLabelText('Ativo')).toBeInTheDocument()
    expect(screen.queryByLabelText('Situação')).not.toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'Manutenção' })).not.toBeInTheDocument()
  })

  it('desmarcar o checkbox salva ativo=false e nao manda status', async () => {
    obter.mockResolvedValue(APARELHO)
    atualizar.mockResolvedValue({ ...APARELHO, ativo: false })
    editar()
    const check = await screen.findByLabelText('Ativo')
    await userEvent.click(check)
    await userEvent.click(screen.getByRole('button', { name: /salvar/i }))
    expect(atualizar).toHaveBeenCalledTimes(1)
    const [, payload] = atualizar.mock.calls[0]
    expect(payload.ativo).toBe(false)
    expect(payload).not.toHaveProperty('status')
  })

  it('mostra o estado por extenso ao lado do interruptor', async () => {
    obter.mockResolvedValue({ ...APARELHO, ativo: true })
    editar()
    expect(await screen.findByRole('switch')).toBeInTheDocument()
    expect(screen.getByText('Ativo')).toBeInTheDocument()
  })

  it('mostra Inativo quando o aparelho esta desativado', async () => {
    obter.mockResolvedValue({ ...APARELHO, ativo: false })
    editar()
    expect(await screen.findByText('Inativo')).toBeInTheDocument()
  })
})
