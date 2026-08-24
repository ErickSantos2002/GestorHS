import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

let mockUser: { funcao: string } | null = { funcao: 'Laboratório' }
vi.mock('../../auth/AuthContext', () => ({ useAuth: () => ({ user: mockUser }) }))

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
vi.mock('./manutencao', async (orig) => {
  const real = await orig<typeof import('./manutencao')>()
  return {
    ...real,
    manutencaoApi: {
      ...real.manutencaoApi,
      obter: vi.fn().mockRejectedValue(new Error('404')),
      listarServicos: vi.fn().mockResolvedValue([]),
    },
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
    nota_fiscal_xml: null, nota_fiscal_numero: null,
    certificado_modelos_faltantes: [], pilhas: 0, bocais: 0, checklist_ids: [],
    acessorios_presentes: [], garantias: null, desfecho_lab: null, desfecho_lab_obs: null,
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

// As duas seções deixam explícito qual documento está sendo feito e onde.
describe('OrdemDetailPage — seções de certificado', () => {
  beforeEach(() => {
    mockUser = { funcao: 'Laboratório' }
    obter.mockReset(); logs.mockReset(); certificados.mockReset()
    logs.mockResolvedValue([]); certificados.mockResolvedValue([])
  })

  it('OS de calibração mostra só a seção de calibração', async () => {
    obter.mockResolvedValue(baseOs({ tipo_servico: 'C' }))
    tela()
    expect(await screen.findByText('Certificado de calibração')).toBeInTheDocument()
    expect(screen.queryByText('Certificado de manutenção')).not.toBeInTheDocument()
  })

  it('OS de manutenção mostra só a seção de manutenção', async () => {
    obter.mockResolvedValue(baseOs({ tipo_servico: 'M' }))
    tela()
    expect(await screen.findByText('Certificado de manutenção')).toBeInTheDocument()
    expect(screen.queryByText('Certificado de calibração')).not.toBeInTheDocument()
  })

  it('OS "Ambas" mostra as duas', async () => {
    obter.mockResolvedValue(baseOs({ tipo_servico: 'A' }))
    tela()
    expect(await screen.findByText('Certificado de calibração')).toBeInTheDocument()
    expect(screen.getByText('Certificado de manutenção')).toBeInTheDocument()
  })

  it('OS antiga sem tipo de serviço mostra a de calibração', async () => {
    obter.mockResolvedValue(baseOs({ tipo_servico: null }))
    tela()
    expect(await screen.findByText('Certificado de calibração')).toBeInTheDocument()
    expect(screen.queryByText('Certificado de manutenção')).not.toBeInTheDocument()
  })

  it('OS de manutenção sem modelo cadastrado mostra o aviso e o link, mesmo sem a seção de calibração', async () => {
    obter.mockResolvedValue(baseOs({ tipo_servico: 'M', certificado_modelos_faltantes: ['M'] }))
    tela()
    expect(await screen.findByText(/não tem modelo de certificado de Manutenção cadastrado/)).toBeInTheDocument()
    expect(screen.getByText('Cadastrar modelo de certificado')).toBeInTheDocument()
  })

  // Regressão: as seções vinham só do tipo_servico, então trocar o tipo depois de
  // gerar (A→M pelo /editar, C→M no laboratório) tirava da tela um documento já
  // emitido — que continua existindo e precisa continuar baixável.
  it('certificado de calibração já emitido continua visível em OS que virou manutenção', async () => {
    obter.mockResolvedValue(baseOs({ tipo_servico: 'M' }))
    certificados.mockResolvedValue([
      { id: 9, os: 500, tipo: 'C', data_geracao: '2026-08-20T12:00:00Z', gerado_por: 'lab' },
    ])
    tela()
    expect(await screen.findByText('Certificado de calibração')).toBeInTheDocument()
    expect(screen.getByText('Certificado de manutenção')).toBeInTheDocument()
    expect(screen.getAllByText('Baixar PDF').length).toBeGreaterThan(0)
    expect(screen.queryByText('Nenhum certificado de calibração gerado.')).not.toBeInTheDocument()
  })

  it('OS de manutenção liberada sem certificado mostra "Liberado sem certificado" e não manda registrar manutenção', async () => {
    obter.mockResolvedValue(baseOs({ tipo_servico: 'M', desfecho_lab: 'liberado' }))
    tela()
    expect(await screen.findByText(/Liberado sem certificado/)).toBeInTheDocument()
    expect(screen.queryByText(/Registre a manutenção antes de gerar/)).not.toBeInTheDocument()
  })
})
