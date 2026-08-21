import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

const { certificadoCampos, gerarCertificado } = vi.hoisted(() => ({
  certificadoCampos: vi.fn(), gerarCertificado: vi.fn(),
}))
vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return { ...real, ordensApi: { ...real.ordensApi, certificadoCampos, gerarCertificado } }
})

import { GerarCertificadoModal } from './GerarCertificadoModal'

const CAMPOS = {
  nomecli: 'ACME', cnpj: '36312056000552', endcli: 'Rua X, 10',
  modelo: 'iBlow10', marca: 'Sentech', serie: 'SN-1', patrimonio: '', datacompra: '2024-01-10',
  calib_cert: null, calib_temp: null, calib_pressao: null, calib_teste1: null,
  calib_teste2: null, calib_teste3: null, calib_teste4: null, calib_teste5: null,
  calib_teste_media: null, calib_situacao: null, data_calibracao: null,
}

function os(tipo: string) {
  return { id: 7, tipo_servico: tipo, equipamento_descricao: 'iBlow10' } as never
}

describe('GerarCertificadoModal — por tipo de serviço', () => {
  beforeEach(() => {
    certificadoCampos.mockReset(); gerarCertificado.mockReset()
    certificadoCampos.mockResolvedValue(CAMPOS)
  })

  it('OS de manutenção mostra os dados do cliente e do aparelho, editáveis', async () => {
    render(<GerarCertificadoModal os={os('M')} onClose={vi.fn()} onGerado={vi.fn()} />)
    const nome = (await screen.findByLabelText(/^nome$/i)) as HTMLInputElement
    expect(nome.value).toBe('ACME')
    expect(nome).not.toBeDisabled()
  })

  it('OS de manutenção NÃO mostra o bloco de calibração', async () => {
    render(<GerarCertificadoModal os={os('M')} onClose={vi.fn()} onGerado={vi.fn()} />)
    await screen.findByLabelText(/^nome$/i)
    expect(screen.queryByLabelText(/teste 1/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/^situação$/i)).not.toBeInTheDocument()
  })

  it('OS de calibração continua mostrando o bloco de calibração', async () => {
    render(<GerarCertificadoModal os={os('C')} onClose={vi.fn()} onGerado={vi.fn()} />)
    expect(await screen.findByLabelText(/teste 1/i)).toBeInTheDocument()
  })

  it('OS "Ambas" mostra o bloco de calibração', async () => {
    render(<GerarCertificadoModal os={os('A')} onClose={vi.fn()} onGerado={vi.fn()} />)
    expect(await screen.findByLabelText(/teste 1/i)).toBeInTheDocument()
  })
})
