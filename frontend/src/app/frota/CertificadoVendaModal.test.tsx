import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('./api', () => ({
  equipamentosClienteApi: {
    certificadoVendaCampos: vi.fn(),
    gerarCertificadoVenda: vi.fn(),
  },
}))
vi.mock('../certificados/api', () => ({
  certificadosApi: {
    calculoPrevia: vi.fn(),
    padroes: vi.fn(),
  },
}))

import { equipamentosClienteApi } from './api'
import { certificadosApi } from '../certificados/api'
import { CertificadoVendaModal } from './CertificadoVendaModal'

const CAMPOS = {
  nomecli: 'ACME', cnpj: '12345678000199', endcli: 'Rua 1',
  modelo: 'Bafômetro X', marca: 'Marca', serie: 'SN1', patrimonio: 'PAT1',
  datacompra: '2026-01-01', calib_cert: null, data_calibracao: '2026-07-01',
  prox_calibragem: null, calib_temp: null, calib_pressao: null,
  calib_teste1: '0,10', calib_teste2: '0,15', calib_teste3: '0,18',
  calib_teste4: '0,16', calib_teste5: '0,17',
  calib_teste_media: null, calib_situacao: null, ja_gerado: false,
}

async function abrirModal() {
  render(<CertificadoVendaModal aparelhoId={1} onClose={() => {}} onGerado={() => {}} />)
  await screen.findByLabelText('Teste 1')
}

describe('CertificadoVendaModal', () => {
  beforeEach(() => {
    vi.mocked(equipamentosClienteApi.certificadoVendaCampos).mockResolvedValue(CAMPOS)
    vi.mocked(equipamentosClienteApi.gerarCertificadoVenda).mockResolvedValue({})
    vi.mocked(certificadosApi.padroes).mockResolvedValue([])
    vi.mocked(certificadosApi.calculoPrevia).mockResolvedValue({
      erros: ['', '', '', '', ''], media: '', desvio_padrao: '', incerteza_combinada: '',
      incerteza_expandida: '', fator_k: '2', limite_minimo: '', limite_maximo: '',
      fora_da_faixa: [false, false, false, false, false],
    })
  })

  it('renderiza os cinco campos de medicao, prefilados com t4/t5 vindos do backend', async () => {
    await abrirModal()
    expect(screen.getByLabelText('Teste 4')).toBeInTheDocument()
    expect(screen.getByLabelText('Teste 5')).toBeInTheDocument()
    expect((screen.getByLabelText('Teste 4') as HTMLInputElement).value).toBe('0,16')
    expect((screen.getByLabelText('Teste 5') as HTMLInputElement).value).toBe('0,17')
  })

  it('envia calib_teste4 e calib_teste5 no payload ao gerar', async () => {
    await abrirModal()
    fireEvent.click(screen.getByRole('button', { name: 'Gerar' }))
    await waitFor(() => expect(equipamentosClienteApi.gerarCertificadoVenda).toHaveBeenCalledTimes(1))
    const [, payload] = vi.mocked(equipamentosClienteApi.gerarCertificadoVenda).mock.calls[0]
    expect(payload.calib_teste4).toBe('0,16')
    expect(payload.calib_teste5).toBe('0,17')
  })
})
