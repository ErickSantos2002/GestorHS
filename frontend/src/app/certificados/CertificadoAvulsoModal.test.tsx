import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('./api', () => ({
  certificadosApi: {
    listarModelos: vi.fn(),
    gerarAvulso: vi.fn(),
    calculoPrevia: vi.fn(),
    padroes: vi.fn(),
  },
}))

import { certificadosApi } from './api'
import { CertificadoAvulsoModal } from './CertificadoAvulsoModal'

const MODELOS = [
  { equipamento: 1, equipamento_descricao: 'Bafômetro X', tem_calibracao: true, tem_manutencao: false },
]

const PREVIA_VAZIA = {
  erros: ['', '', '', '', ''], media: '', desvio_padrao: '', incerteza_combinada: '',
  incerteza_expandida: '', fator_k: '2', limite_minimo: '', limite_maximo: '',
  fora_da_faixa: [false, false, false, false, false],
}

async function abrirModal() {
  render(<CertificadoAvulsoModal onClose={() => {}} onGerado={() => {}} />)
  await screen.findByLabelText('Modelo do aparelho')
}

describe('CertificadoAvulsoModal', () => {
  beforeEach(() => {
    vi.mocked(certificadosApi.listarModelos).mockResolvedValue({ items: MODELOS })
    vi.mocked(certificadosApi.padroes).mockResolvedValue([])
    vi.mocked(certificadosApi.calculoPrevia).mockResolvedValue(PREVIA_VAZIA)
    vi.mocked(certificadosApi.gerarAvulso).mockResolvedValue({
      id: 1, tipo: 'C', nomecli: null, serie: null, calib_cert: null,
      data_calibracao: null, data_geracao: null, usuario_nome: null,
    })
  })

  it('renderiza os campos Teste 1 a Teste 5', async () => {
    await abrirModal()
    expect(screen.getByLabelText('Teste 1')).toBeInTheDocument()
    expect(screen.getByLabelText('Teste 2')).toBeInTheDocument()
    expect(screen.getByLabelText('Teste 3')).toBeInTheDocument()
    expect(screen.getByLabelText('Teste 4')).toBeInTheDocument()
    expect(screen.getByLabelText('Teste 5')).toBeInTheDocument()
  })

  it('envia calib_teste4 e calib_teste5 no payload ao gerar', async () => {
    await abrirModal()
    fireEvent.change(screen.getByLabelText('Modelo do aparelho'), { target: { value: '1:C' } })
    fireEvent.change(screen.getByLabelText('Teste 1'), { target: { value: '0,10' } })
    fireEvent.change(screen.getByLabelText('Teste 2'), { target: { value: '0,15' } })
    fireEvent.change(screen.getByLabelText('Teste 3'), { target: { value: '0,18' } })
    fireEvent.change(screen.getByLabelText('Teste 4'), { target: { value: '0,16' } })
    fireEvent.change(screen.getByLabelText('Teste 5'), { target: { value: '0,17' } })

    fireEvent.click(screen.getByRole('button', { name: 'Gerar' }))

    await waitFor(() => expect(certificadosApi.gerarAvulso).toHaveBeenCalledTimes(1))
    const payload = vi.mocked(certificadosApi.gerarAvulso).mock.calls[0][0]
    expect(payload.calib_teste4).toBe('0,16')
    expect(payload.calib_teste5).toBe('0,17')
    expect(payload.calib_teste1).toBe('0,10')
  })

  it('calcula a media sobre as medicoes preenchidas, sem exigir as cinco', async () => {
    await abrirModal()
    fireEvent.change(screen.getByLabelText('Teste 1'), { target: { value: '0,10' } })
    fireEvent.change(screen.getByLabelText('Teste 2'), { target: { value: '0,20' } })
    fireEvent.change(screen.getByLabelText('Teste 3'), { target: { value: '0,30' } })
    expect((screen.getByLabelText('Média dos testes') as HTMLInputElement).value).toBe('0,200')
  })

  it('mostra o painel de calculo (incerteza expandida) quando a previa retorna', async () => {
    vi.mocked(certificadosApi.calculoPrevia).mockResolvedValue({
      ...PREVIA_VAZIA,
      erros: ['0,06', '0,06', '0,06', '0,06', '0,06'],
      incerteza_expandida: '0,1301',
    })
    await abrirModal()
    fireEvent.change(screen.getByLabelText('Teste 1'), { target: { value: '0,16' } })
    await waitFor(() => expect(screen.getByText('0,1301')).toBeInTheDocument())
  })

  it('nao mostra o aviso de cilindro ao abrir o modal, antes de o operador digitar algo', async () => {
    // Data de calibracao vem pre-preenchida com hoje (igual OS e venda), entao um
    // cilindro vigente cadastrado ja resolve de cara — sem o aviso ambar de
    // "nenhum cilindro cobre esta data" antes mesmo de o operador digitar algo.
    vi.mocked(certificadosApi.padroes).mockResolvedValue([{
      id: 1, numero_cilindro: 'CC747704', numero_certificado: '202231419',
      concentracao: '100.1000', incerteza_concentracao: '2.0000', unidade: 'µmol/mol',
      vigencia_inicio: '2020-01-01', vigencia_fim: null, ativo: true,
    }])
    await abrirModal()
    await waitFor(() => expect(screen.getByText(/Cilindro que será gravado/)).toBeInTheDocument())
    expect(screen.queryByText(/Nenhum cilindro cadastrado cobre esta data/)).not.toBeInTheDocument()
  })
})
