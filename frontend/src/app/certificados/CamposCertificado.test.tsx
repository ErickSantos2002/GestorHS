import { useState } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { CamposCertificado } from './CamposCertificado'
import { valoresIniciais, type ValoresCertificado } from './valoresCertificado'

vi.mock('./api', () => ({
  certificadosApi: {
    calculoPrevia: vi.fn(),
    padroes: vi.fn(),
  },
}))

import { certificadosApi } from './api'

function Harness({ extra, medicoes, iniciais }: {
  extra?: React.ReactNode
  medicoes?: 3 | 5
  iniciais?: Partial<ValoresCertificado>
}) {
  const [v, setV] = useState<ValoresCertificado>({ ...valoresIniciais(), ...iniciais })
  return <CamposCertificado valores={v} onChange={(p) => setV((a) => ({ ...a, ...p }))} extra={extra} medicoes={medicoes} />
}

const CILINDRO = {
  id: 7, numero_cilindro: 'CC747704', numero_certificado: '202231419',
  concentracao: '100.1000', incerteza_concentracao: '2.0000', unidade: 'µmol/mol',
  vigencia_inicio: '2020-01-01', vigencia_fim: null, ativo: true,
}

describe('CamposCertificado', () => {
  beforeEach(() => {
    vi.mocked(certificadosApi.padroes).mockResolvedValue([])
  })

  it('mostra as tres secoes do formulario', () => {
    render(<Harness />)
    expect(screen.getByText('Cliente')).toBeInTheDocument()
    expect(screen.getByText('Aparelho')).toBeInTheDocument()
    expect(screen.getByText('Calibração')).toBeInTheDocument()
  })

  it('calcula a media dos testes automaticamente', () => {
    render(<Harness />)
    fireEvent.change(screen.getByLabelText('Teste 1'), { target: { value: '0,10' } })
    fireEvent.change(screen.getByLabelText('Teste 2'), { target: { value: '0,20' } })
    fireEvent.change(screen.getByLabelText('Teste 3'), { target: { value: '0,30' } })
    // mediaTestes remove zeros a direita por design (0,200 -> 0,2)
    expect((screen.getByLabelText('Média dos testes') as HTMLInputElement).value).toBe('0,200')
  })

  it('para de calcular a media depois que o usuario digita a mao', () => {
    render(<Harness />)
    fireEvent.change(screen.getByLabelText('Média dos testes'), { target: { value: '9,99' } })
    fireEvent.change(screen.getByLabelText('Teste 1'), { target: { value: '0,10' } })
    expect((screen.getByLabelText('Média dos testes') as HTMLInputElement).value).toBe('9,99')
  })

  it('renderiza o slot extra no fim da secao de calibracao', () => {
    render(<Harness extra={<p>campo extra</p>} />)
    expect(screen.getByText('campo extra')).toBeInTheDocument()
  })

  const PREVIA_OK = {
    erros: ['0,060', '0,060', '0,060', '0,060', '0,060'], media: '0,160', desvio_padrao: '0',
    incerteza_combinada: '0,0651', incerteza_expandida: '0,1301', fator_k: '2',
    limite_minimo: '0,150', limite_maximo: '0,190', fora_da_faixa: [false, false, false, false, false],
  }

  it('mostra cinco campos de medicao quando medicoes=5', async () => {
    render(<CamposCertificado valores={valoresIniciais()} onChange={() => {}} medicoes={5} />)
    expect(screen.getByLabelText('Teste 1')).toBeInTheDocument()
    expect(screen.getByLabelText('Teste 4')).toBeInTheDocument()
    expect(screen.getByLabelText('Teste 5')).toBeInTheDocument()
    await screen.findByText(/Nenhum cilindro cadastrado cobre esta data/i)   // assenta a busca de cilindros
  })

  it('fica em tres campos por padrao — venda e avulso nao aceitam cinco', () => {
    // Sem a prop, o componente NAO pode oferecer campo que o backend descarta:
    // os schemas de venda e avulso so tem calib_teste1..3.
    render(<CamposCertificado valores={valoresIniciais()} onChange={() => {}} />)
    expect(screen.getByLabelText('Teste 3')).toBeInTheDocument()
    expect(screen.queryByLabelText('Teste 4')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Teste 5')).not.toBeInTheDocument()
  })

  it('destaca medicao fora da faixa sem impedir a geracao', async () => {
    vi.mocked(certificadosApi.calculoPrevia).mockResolvedValue({
      ...PREVIA_OK,
      erros: ['0,060', '', '', '', ''],
      fora_da_faixa: [true, false, false, false, false],
    })
    const valores = { ...valoresIniciais(), t1: '0.016' }
    render(<CamposCertificado valores={valores} onChange={() => {}} medicoes={5} />)
    await waitFor(() => expect(screen.getByText(/fora da faixa/i)).toBeInTheDocument())
    // o aviso NAO desabilita nada: o certificado de aparelho reprovado tambem precisa existir
    expect(screen.getByLabelText('Teste 1')).not.toBeDisabled()
  })

  it('exibe a incerteza expandida vinda do backend', async () => {
    vi.mocked(certificadosApi.calculoPrevia).mockResolvedValue(PREVIA_OK)
    const valores = { ...valoresIniciais(), t1: '0.16', t2: '0.16', t3: '0.16', t4: '0.16', t5: '0.16' }
    render(<CamposCertificado valores={valores} onChange={() => {}} medicoes={5} />)
    await waitFor(() => expect(screen.getByText('0,1301')).toBeInTheDocument())
  })

  it('calcula a media so com as medicoes preenchidas — OS antiga nao perde a media', async () => {
    // Regressao: com medicoes=5 e t4/t5 em branco (toda OS anterior ao EPS-LAB-002),
    // a media era zerada na montagem do modal e o Gerar apagava calib_teste_media no banco.
    render(<Harness medicoes={5} />)
    fireEvent.change(screen.getByLabelText('Teste 1'), { target: { value: '0,10' } })
    fireEvent.change(screen.getByLabelText('Teste 2'), { target: { value: '0,20' } })
    fireEvent.change(screen.getByLabelText('Teste 3'), { target: { value: '0,30' } })
    const media = screen.getByLabelText('Média dos testes') as HTMLInputElement
    expect(media.value).toBe('0,200')
    expect(media.value).not.toBe('')
    await screen.findByText(/Nenhum cilindro cadastrado cobre esta data/i)   // assenta a busca de cilindros
  })

  it('nao apaga a media que veio gravada antes de o usuario mexer nas medicoes', async () => {
    render(<Harness medicoes={5} iniciais={{ t1: '0,16', t2: '0,16', t3: '0,16', media: '0,163' }} />)
    expect((screen.getByLabelText('Média dos testes') as HTMLInputElement).value).toBe('0,163')
    await screen.findByText(/Nenhum cilindro cadastrado cobre esta data/i)
  })

  it('mostra o cilindro que sera gravado no certificado', async () => {
    vi.mocked(certificadosApi.padroes).mockResolvedValue([CILINDRO])
    render(<Harness medicoes={5} iniciais={{ dataCalib: '2026-07-31' }} />)
    await waitFor(() => expect(screen.getByText('CC747704')).toBeInTheDocument())
    expect(screen.getByText(/certificado 202231419/)).toBeInTheDocument()
  })

  it('avisa quando nenhum cilindro cobre a data da calibracao, sem bloquear', async () => {
    vi.mocked(certificadosApi.padroes).mockResolvedValue([
      { ...CILINDRO, vigencia_inicio: '2026-01-01', vigencia_fim: '2026-06-30' },
    ])
    render(<Harness medicoes={5} iniciais={{ dataCalib: '2026-07-31' }} />)
    await waitFor(() => expect(screen.getByText(/Nenhum cilindro cadastrado cobre esta data/i)).toBeInTheDocument())
    expect(screen.getByLabelText('Teste 1')).not.toBeDisabled()
  })

  it('nao busca os cilindros quando esta em tres medicoes', async () => {
    vi.mocked(certificadosApi.padroes).mockClear()
    render(<Harness />)
    await new Promise((r) => setTimeout(r, 50))
    expect(certificadosApi.padroes).not.toHaveBeenCalled()
  })

  it('nao chama a previa quando esta em tres medicoes', async () => {
    vi.mocked(certificadosApi.calculoPrevia).mockClear()
    const valores = { ...valoresIniciais(), t1: '0.16', t2: '0.16', t3: '0.16' }
    render(<CamposCertificado valores={valores} onChange={() => {}} />)
    await new Promise((r) => setTimeout(r, 500))   // passa do debounce de 400ms
    expect(certificadosApi.calculoPrevia).not.toHaveBeenCalled()
  })
})
