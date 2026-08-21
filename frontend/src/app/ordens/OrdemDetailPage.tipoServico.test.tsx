import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

let mockUser: { funcao: string } | null = { funcao: 'Laboratório' }
vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ user: mockUser }),
}))

const { obter, logs, certificados, editarTipoServico } = vi.hoisted(() => ({
  obter: vi.fn(), logs: vi.fn(), certificados: vi.fn(), editarTipoServico: vi.fn(),
}))
vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return {
    ...real,
    ordensApi: { ...real.ordensApi, obter, logs, certificados, editarTipoServico },
    fotosApi: { ...real.fotosApi, listar: vi.fn().mockResolvedValue([]) },
  }
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
    nota_fiscal_xml: null,
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

// A Expedicao registra o tipo na entrada pelo que ve por fora; o tecnico e quem
// descobre na bancada que o aparelho tambem precisa de manutencao.
describe('OrdemDetailPage — tipo de serviço', () => {
  beforeEach(() => {
    mockUser = { funcao: 'Laboratório' }
    obter.mockReset(); logs.mockReset(); certificados.mockReset(); editarTipoServico.mockReset()
    logs.mockResolvedValue([])
    certificados.mockResolvedValue([])
  })

  it('laboratório troca o tipo com a OS na fase dele', async () => {
    obter.mockResolvedValue(baseOs())
    editarTipoServico.mockResolvedValue(baseOs({ tipo_servico: 'M' }))
    tela()

    const select = await screen.findByLabelText('Tipo de serviço')
    expect((select as HTMLSelectElement).value).toBe('C')

    await userEvent.selectOptions(select, 'M')

    await waitFor(() => expect(editarTipoServico).toHaveBeenCalledWith(500, 'M'))
    await waitFor(() => expect((screen.getByLabelText('Tipo de serviço') as HTMLSelectElement).value).toBe('M'))
  })

  it('fora da fase do laboratório o campo é só leitura', async () => {
    obter.mockResolvedValue(baseOs({ fase: 6, fase_descricao: 'Pós-Vendas' }))
    tela()

    await screen.findByText('Recebimento')
    expect(screen.queryByLabelText('Tipo de serviço')).not.toBeInTheDocument()
    expect(screen.getAllByText('Calibração').length).toBeGreaterThan(0)
  })

  it('outra função não edita, mesmo na fase do laboratório', async () => {
    mockUser = { funcao: 'Financeiro' }
    obter.mockResolvedValue(baseOs())
    tela()

    await screen.findByText('Recebimento')
    expect(screen.queryByLabelText('Tipo de serviço')).not.toBeInTheDocument()
    expect(screen.getAllByText('Calibração').length).toBeGreaterThan(0)
  })

  it('erro do servidor aparece na tela e o valor não muda', async () => {
    const { ApiError } = await import('../../lib/api')
    obter.mockResolvedValue(baseOs())
    editarTipoServico.mockRejectedValue(new ApiError(409, 'o tipo de serviço só pode ser corrigido enquanto a OS está no Laboratório'))
    tela()

    await userEvent.selectOptions(await screen.findByLabelText('Tipo de serviço'), 'A')

    expect(await screen.findByText(/só pode ser corrigido/)).toBeInTheDocument()
  })
})
