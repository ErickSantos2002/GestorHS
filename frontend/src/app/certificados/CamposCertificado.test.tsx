import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { CamposCertificado } from './CamposCertificado'
import { valoresIniciais, type ValoresCertificado } from './valoresCertificado'

vi.mock('./api', () => ({
  certificadosApi: {
    calculoPrevia: vi.fn(),
  },
}))

import { certificadosApi } from './api'

function Harness({ extra }: { extra?: React.ReactNode }) {
  const [v, setV] = useState<ValoresCertificado>(valoresIniciais())
  return <CamposCertificado valores={v} onChange={(p) => setV((a) => ({ ...a, ...p }))} extra={extra} />
}

describe('CamposCertificado', () => {
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
    expect((screen.getByLabelText('Média dos testes') as HTMLInputElement).value).toBe('0,2')
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
    erros: ['0,06', '0,06', '0,06', '0,06', '0,06'], media: '0,16', desvio_padrao: '0',
    incerteza_combinada: '0,0651', incerteza_expandida: '0,1301', fator_k: '2',
    limite_minimo: '0,15', limite_maximo: '0,19', fora_da_faixa: [false, false, false, false, false],
  }

  it('mostra cinco campos de medicao quando medicoes=5', () => {
    render(<CamposCertificado valores={valoresIniciais()} onChange={() => {}} medicoes={5} />)
    expect(screen.getByLabelText('Teste 1')).toBeInTheDocument()
    expect(screen.getByLabelText('Teste 4')).toBeInTheDocument()
    expect(screen.getByLabelText('Teste 5')).toBeInTheDocument()
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
      erros: ['0,06', '', '', '', ''],
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

  it('nao chama a previa quando esta em tres medicoes', async () => {
    vi.mocked(certificadosApi.calculoPrevia).mockClear()
    const valores = { ...valoresIniciais(), t1: '0.16', t2: '0.16', t3: '0.16' }
    render(<CamposCertificado valores={valores} onChange={() => {}} />)
    await new Promise((r) => setTimeout(r, 500))   // passa do debounce de 400ms
    expect(certificadosApi.calculoPrevia).not.toHaveBeenCalled()
  })
})
