import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { CamposCertificado } from './CamposCertificado'
import { valoresIniciais, type ValoresCertificado } from './valoresCertificado'

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
})
