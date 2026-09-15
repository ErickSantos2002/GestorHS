import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { useState } from 'react'

const buscarCep = vi.fn()
const buscarCnpj = vi.fn()
vi.mock('./buscaEndereco', async (orig) => {
  const real = await orig<typeof import('./buscaEndereco')>()
  return { ...real, buscaApi: { cep: (...a: unknown[]) => buscarCep(...a), cnpj: (...a: unknown[]) => buscarCnpj(...a) } }
})

import { DadosEmpresaForm } from './DadosEmpresaForm'
import { dadosVazios, type DadosEmpresa } from './dadosEmpresa'

function Harness(props: Partial<React.ComponentProps<typeof DadosEmpresaForm>> & { inicial?: Partial<DadosEmpresa> }) {
  const [dados, setDados] = useState<DadosEmpresa>({ ...dadosVazios(), ...props.inicial })
  return (
    <>
      <DadosEmpresaForm {...props} dados={dados} onChange={setDados} />
      <output data-testid="estado">{JSON.stringify(dados)}</output>
    </>
  )
}
const estado = () => JSON.parse(screen.getByTestId('estado').textContent ?? '{}') as DadosEmpresa

describe('DadosEmpresaForm', () => {
  beforeEach(() => { buscarCep.mockReset(); buscarCnpj.mockReset() })

  it('edita os campos', () => {
    render(<Harness />)
    fireEvent.change(screen.getByLabelText(/Bairro/), { target: { value: 'Centro' } })
    expect(estado().bairro).toBe('Centro')
  })

  it('documento travado fica somente leitura', () => {
    render(<Harness documentoTravado inicial={{ documento: '08857492000148' }} />)
    const doc = screen.getByLabelText(/CNPJ \/ CPF/) as HTMLInputElement
    expect(doc.readOnly).toBe(true)
    expect(doc.value).toBe('08.857.492/0001-48')
  })

  it('sugestao de e-mail preenche com um clique', () => {
    render(<Harness sugestoes={{ email: 'a@acme.com' }} />)
    fireEvent.click(screen.getByRole('button', { name: /Usar do cadastro: a@acme.com/ }))
    expect(estado().email).toBe('a@acme.com')
  })

  it('sugestao some quando o campo ja tem o mesmo valor', () => {
    render(<Harness sugestoes={{ telefone: '8130001111' }} inicial={{ telefone: '8130001111' }} />)
    expect(screen.queryByRole('button', { name: /Usar do cadastro/ })).toBeNull()
  })

  it('lupa do CNPJ preenche numero e bairro e permite desfazer', async () => {
    buscarCnpj.mockResolvedValue({
      documento: '36312056000552', nome: 'CBF', cep: '29680000', endereco: 'BR 101', numero: 'S/N',
      complemento: 'KM 196', bairro: 'Zona Rural', municipio: 'Joao Neiva', estado: 'ES', situacao: 'ATIVA',
    })
    render(<Harness inicial={{ documento: '36312056000552' }} />)
    fireEvent.click(screen.getByRole('button', { name: 'Buscar dados pelo CNPJ' }))
    await waitFor(() => expect(estado().bairro).toBe('Zona Rural'))
    expect(estado().numero).toBe('S/N')
    fireEvent.click(screen.getByRole('button', { name: 'Desfazer' }))
    expect(estado().bairro).toBe('')
  })

  it('somente leitura desabilita campos e lupas', () => {
    render(<Harness somenteLeitura />)
    expect((screen.getByLabelText(/Razão social/) as HTMLInputElement).disabled).toBe(true)
    expect(screen.queryByRole('button', { name: 'Buscar dados pelo CNPJ' })).toBeNull()
  })

  it('destaca obrigatorio vazio', () => {
    render(<Harness obrigatorios={['nome']} destacarFaltando />)
    expect(screen.getByLabelText(/Razão social \/ Nome \*/).className).toContain('border-danger')
  })
})
