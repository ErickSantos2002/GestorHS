import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

let mockUser: { funcao: string } | null = { funcao: 'Laboratório' }
vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ user: mockUser }),
}))

const { obter, logs, certificados } = vi.hoisted(() => ({
  obter: vi.fn(), logs: vi.fn(), certificados: vi.fn(),
}))
vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return {
    ...real,
    ordensApi: { ...real.ordensApi, obter, logs, certificados },
    fotosApi: { ...real.fotosApi, listar: vi.fn().mockResolvedValue([]) },
  }
})

const { desfechoLab } = vi.hoisted(() => ({ desfechoLab: vi.fn() }))
vi.mock('../caixas/api', async (orig) => {
  const real = await orig<typeof import('../caixas/api')>()
  return { ...real, caixasApi: { ...real.caixasApi, desfechoLab } }
})

import { OrdemDetailPage } from './OrdemDetailPage'

function baseOs(over: Record<string, unknown> = {}) {
  return {
    id: 500, cliente: 1, cliente_nome: 'ACME', equipamento_cliente: 1,
    equipamento_descricao: 'IBLOW10D', equipamento_serie: 'SN-1', fase: 5,
    fase_descricao: 'Laboratório', fase_cor: 'abc123', tipo_servico: 'C',
    data_chegada: null, prox_calibragem: null, situacao: 'A', caixa: null,
    condicao_chegada: null, acessorios: null, aceite: false, recebido: true,
    etiqueta: null, cod_retorno: null, obs: null, data_calibracao: null,
    data_retorno: null, data_aceite: null, tipo_calibragem: null,
    calib_cert: null, calib_temp: null, calib_pressao: null, calib_teste1: null,
    calib_teste2: null, calib_teste3: null, calib_teste_media: null,
    calib_situacao: null, pdf_certificado: null, nota_fiscal: null,
    nota_fiscal_numero: null, notas_fiscais: [], certificado_modelos_faltantes: [], pilhas: 0,
    bocais: 0, checklist_ids: [], acessorios_presentes: [], garantias: null,
    desfecho_lab: 'pendente', desfecho_lab_obs: null,
    ...over,
  }
}

function tela() {
  return render(
    <MemoryRouter initialEntries={['/app/ordens/500']}>
      <Routes><Route path="/app/ordens/:id" element={<OrdemDetailPage />} /></Routes>
    </MemoryRouter>,
  )
}

describe('OrdemDetailPage — Liberar do Laboratório', () => {
  beforeEach(() => {
    mockUser = { funcao: 'Laboratório' }
    obter.mockReset(); logs.mockReset(); certificados.mockReset(); desfechoLab.mockReset()
    logs.mockResolvedValue([])
    certificados.mockResolvedValue([])
    desfechoLab.mockResolvedValue({})
  })

  it('mostra o botão para Laboratório quando fase=5 e desfecho_lab pendente', async () => {
    obter.mockResolvedValue(baseOs())
    tela()
    expect(await screen.findByRole('button', { name: 'Liberar do Laboratório' })).toBeInTheDocument()
  })

  it('não mostra o botão para Expedição', async () => {
    mockUser = { funcao: 'Expedição' }
    obter.mockResolvedValue(baseOs())
    tela()
    await screen.findByText('OS #500')
    expect(screen.queryByRole('button', { name: 'Liberar do Laboratório' })).toBeNull()
  })

  it('não mostra o botão quando desfecho_lab já não está pendente', async () => {
    obter.mockResolvedValue(baseOs({ desfecho_lab: 'concluido' }))
    tela()
    await screen.findByText('OS #500')
    expect(screen.queryByRole('button', { name: 'Liberar do Laboratório' })).toBeNull()
  })

  it('abre o modal e envia desfecho liberado com a justificativa preenchida', async () => {
    obter.mockResolvedValue(baseOs())
    tela()
    fireEvent.click(await screen.findByRole('button', { name: 'Liberar do Laboratório' }))

    const textarea = await screen.findByLabelText('Motivo (opcional)')
    fireEvent.change(textarea, { target: { value: 'modelo de manutencao ainda nao cadastrado' } })
    // Depois de abrir o modal existem dois botões com o mesmo rótulo: o do cabeçalho e o do submit do modal.
    fireEvent.click(screen.getAllByRole('button', { name: 'Liberar do Laboratório' })[1])

    await waitFor(() => {
      expect(desfechoLab).toHaveBeenCalledWith(500, { desfecho: 'liberado', obs: 'modelo de manutencao ainda nao cadastrado' })
    })
  })

  it('envia obs:null quando a justificativa fica vazia (é opcional)', async () => {
    obter.mockResolvedValue(baseOs())
    tela()
    fireEvent.click(await screen.findByRole('button', { name: 'Liberar do Laboratório' }))
    await screen.findByLabelText('Motivo (opcional)')

    fireEvent.click(screen.getAllByRole('button', { name: 'Liberar do Laboratório' })[1])

    await waitFor(() => {
      expect(desfechoLab).toHaveBeenCalledWith(500, { desfecho: 'liberado', obs: null })
    })
  })
})
