import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

let mockUser: { funcao: string } | null = { funcao: 'Administrador' }
vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ user: mockUser }),
}))

const { obter, logs, certificados, editar } = vi.hoisted(() => ({
  obter: vi.fn(), logs: vi.fn(), certificados: vi.fn(), editar: vi.fn(),
}))
vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return {
    ...real,
    ordensApi: { ...real.ordensApi, obter, logs, certificados, editar },
    fotosApi: { ...real.fotosApi, listar: vi.fn().mockResolvedValue([]) },
  }
})

import { OrdemDetailPage } from './OrdemDetailPage'

function baseOs(over: Record<string, unknown> = {}) {
  return {
    id: 500, cliente: 1, cliente_nome: 'ACME', equipamento_cliente: 1,
    equipamento_descricao: 'IBLOW10D', equipamento_serie: 'SN-1', fase: 4,
    fase_descricao: 'Recebido', fase_cor: 'abc123', tipo_servico: 'C',
    data_chegada: null, prox_calibragem: null, situacao: 'A', caixa: null,
    condicao_chegada: null, acessorios: null, aceite: false, recebido: true,
    etiqueta: null, cod_retorno: null, obs: null, data_calibracao: null,
    data_retorno: null, data_aceite: null, tipo_calibragem: null,
    calib_cert: null, calib_temp: null, calib_pressao: null, calib_teste1: null,
    calib_teste2: null, calib_teste3: null, calib_teste_media: null,
    calib_situacao: null, pdf_certificado: null, nota_fiscal: null,
    nota_fiscal_numero: null, certificado_modelos_faltantes: [], pilhas: 0,
    bocais: 0, checklist_ids: [], acessorios_presentes: [], garantias: null,
    desfecho_lab: null, desfecho_lab_obs: null,
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

describe('OrdemDetailPage — Editar OS (Admin)', () => {
  beforeEach(() => {
    mockUser = { funcao: 'Administrador' }
    obter.mockReset(); logs.mockReset(); certificados.mockReset(); editar.mockReset()
    logs.mockResolvedValue([])
    certificados.mockResolvedValue([])
  })

  it('mostra o botão "Editar OS" para Administrador', async () => {
    obter.mockResolvedValue(baseOs())
    tela()
    expect(await screen.findByRole('button', { name: 'Editar OS' })).toBeInTheDocument()
  })

  it('não mostra o botão "Editar OS" para outras funções', async () => {
    mockUser = { funcao: 'Expedição' }
    obter.mockResolvedValue(baseOs())
    tela()
    await screen.findByText('OS #500')
    expect(screen.queryByRole('button', { name: 'Editar OS' })).toBeNull()
  })

  it('abre o modal, salva e recarrega a OS', async () => {
    obter.mockResolvedValue(baseOs())
    editar.mockResolvedValue(baseOs({ tipo_servico: 'M' }))
    tela()
    fireEvent.click(await screen.findByRole('button', { name: 'Editar OS' }))

    expect(await screen.findByRole('heading', { name: /editar os/i })).toBeInTheDocument()
    // Escopado ao modal: a pagina por tras tambem tem um botao "Salvar observações"
    // (secao Observações) que casaria com um /salvar/i solto.
    const modal = within(screen.getByTestId('modal-backdrop'))
    fireEvent.click(modal.getByRole('button', { name: /salvar/i }))

    await waitFor(() => expect(editar).toHaveBeenCalledWith(500, expect.anything()))
    await waitFor(() => expect(obter).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(screen.queryByRole('heading', { name: /editar os/i })).toBeNull())
  })
})
