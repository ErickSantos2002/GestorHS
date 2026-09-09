import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

let mockUser: { funcao: string } | null = { funcao: 'Administrador' }
vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ user: mockUser }),
}))

const { obter, logs, certificados, cancelar } = vi.hoisted(() => ({
  obter: vi.fn(), logs: vi.fn(), certificados: vi.fn(), cancelar: vi.fn(),
}))
vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return {
    ...real,
    ordensApi: { ...real.ordensApi, obter, logs, certificados, cancelar },
    fotosApi: { ...real.fotosApi, listar: vi.fn().mockResolvedValue([]) },
  }
})

import { OrdemDetailPage } from './OrdemDetailPage'

function baseOs(over: Record<string, unknown> = {}) {
  return {
    id: 500, cliente: 1, cliente_nome: 'ACME', equipamento_cliente: 1,
    equipamento_descricao: 'IBLOW10D', equipamento_serie: 'SN-1', fase: 5,
    fase_descricao: 'Laboratório', fase_cor: 'abc123', tipo_servico: 'C',
    data_chegada: null, prox_calibragem: null, situacao: 'A', caixa: 3,
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

describe('OrdemDetailPage — Cancelar OS', () => {
  beforeEach(() => {
    mockUser = { funcao: 'Administrador' }
    obter.mockReset(); logs.mockReset(); certificados.mockReset(); cancelar.mockReset()
    logs.mockResolvedValue([])
    certificados.mockResolvedValue([])
    cancelar.mockResolvedValue({})
  })

  it('mostra o botão para o Administrador quando a fase está ativa', async () => {
    obter.mockResolvedValue(baseOs())
    tela()
    expect(await screen.findByRole('button', { name: 'Cancelar OS' })).toBeInTheDocument()
  })

  it('não mostra o botão para o Laboratório', async () => {
    mockUser = { funcao: 'Laboratório' }
    obter.mockResolvedValue(baseOs())
    tela()
    await screen.findByText('OS #500')
    expect(screen.queryByRole('button', { name: 'Cancelar OS' })).toBeNull()
  })

  it('não mostra o botão quando a OS já está cancelada', async () => {
    obter.mockResolvedValue(baseOs({ fase: 9, fase_descricao: 'Cancelada' }))
    tela()
    await screen.findByText('OS #500')
    expect(screen.queryByRole('button', { name: 'Cancelar OS' })).toBeNull()
  })

  it('não mostra o botão quando a OS já foi finalizada', async () => {
    obter.mockResolvedValue(baseOs({ fase: 8, fase_descricao: 'Finalizada' }))
    tela()
    await screen.findByText('OS #500')
    expect(screen.queryByRole('button', { name: 'Cancelar OS' })).toBeNull()
  })

  it('envia o motivo digitado no modal', async () => {
    obter.mockResolvedValue(baseOs())
    tela()
    fireEvent.click(await screen.findByRole('button', { name: 'Cancelar OS' }))

    const textarea = await screen.findByLabelText('Motivo')
    fireEvent.change(textarea, { target: { value: 'aberta em duplicidade' } })
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar a OS' }))

    await waitFor(() => {
      expect(cancelar).toHaveBeenCalledWith(500, { motivo: 'aberta em duplicidade' })
    })
  })

  it('exige o motivo antes de enviar', async () => {
    obter.mockResolvedValue(baseOs())
    tela()
    fireEvent.click(await screen.findByRole('button', { name: 'Cancelar OS' }))
    await screen.findByLabelText('Motivo')

    fireEvent.click(screen.getByRole('button', { name: 'Cancelar a OS' }))

    expect(await screen.findByText('Motivo é obrigatório.')).toBeInTheDocument()
    expect(cancelar).not.toHaveBeenCalled()
  })
})
