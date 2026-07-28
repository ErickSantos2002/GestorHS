import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { ordensApi, type OrdemDetalhe } from './api'
import { EditarOSModal } from './EditarOSModal'

vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return { ...real, ordensApi: { ...real.ordensApi, editar: vi.fn() } }
})

function baseOs(over: Partial<OrdemDetalhe> = {}): OrdemDetalhe {
  return {
    id: 5, cliente: 1, cliente_nome: 'ACME', equipamento_cliente: 1,
    equipamento_descricao: 'IBLOW10D', equipamento_serie: 'SN-1', fase: 4,
    fase_descricao: 'Recebido', fase_cor: 'abc123', tipo_servico: 'M',
    data_chegada: '2026-07-20T12:00:00+00:00', prox_calibragem: null, situacao: 'A', caixa: null,
    condicao_chegada: null, acessorios: null, aceite: false, recebido: true,
    etiqueta: null, cod_retorno: null, obs: '', data_calibracao: null,
    data_retorno: null, data_aceite: null, tipo_calibragem: null,
    calib_cert: null, calib_temp: null, calib_pressao: null, calib_teste1: null,
    calib_teste2: null, calib_teste3: null, calib_teste_media: null,
    calib_situacao: null, pdf_certificado: null, nota_fiscal: null,
    nota_fiscal_numero: null, certificado_modelos_faltantes: [], pilhas: 0,
    bocais: 0, checklist_ids: [], acessorios_presentes: [], garantias: null,
    desfecho_lab: null, desfecho_lab_obs: null,
    ...over,
  } as OrdemDetalhe
}

describe('EditarOSModal', () => {
  beforeEach(() => {
    vi.mocked(ordensApi.editar).mockReset()
    vi.mocked(ordensApi.editar).mockResolvedValue({} as OrdemDetalhe)
  })

  it('pré-preenche os campos com os valores atuais da OS', () => {
    render(<EditarOSModal os={baseOs({ tipo_servico: 'M', pilhas: 2, bocais: 3 })} onClose={() => {}} onSalvo={() => {}} />)
    expect(screen.getByLabelText(/tipo de serviço/i)).toHaveValue('M')
    expect(screen.getByLabelText(/pilhas/i)).toHaveValue(2)
    expect(screen.getByLabelText(/bocais/i)).toHaveValue(3)
  })

  it('submete edicao chamando ordensApi.editar', async () => {
    render(<EditarOSModal os={baseOs({ tipo_servico: 'M' })} onClose={() => {}} onSalvo={() => {}} />)
    fireEvent.change(screen.getByLabelText(/tipo de serviço/i), { target: { value: 'C' } })
    fireEvent.click(screen.getByRole('button', { name: /salvar/i }))
    await waitFor(() => expect(ordensApi.editar).toHaveBeenCalledWith(5, expect.objectContaining({ tipo_servico: 'C' })))
  })

  it('envia observacoes a partir de os.obs e chama onSalvo ao concluir', async () => {
    const onSalvo = vi.fn()
    render(<EditarOSModal os={baseOs({ obs: 'texto antigo' })} onClose={() => {}} onSalvo={onSalvo} />)
    expect(screen.getByDisplayValue('texto antigo')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /salvar/i }))
    await waitFor(() => expect(ordensApi.editar).toHaveBeenCalledWith(5, expect.objectContaining({ observacoes: 'texto antigo' })))
    await waitFor(() => expect(onSalvo).toHaveBeenCalled())
  })
})
