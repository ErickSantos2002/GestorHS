import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ClienteFormFields } from './ClienteFormFields'
import type { ClientePayload } from './api'

const VAZIO: ClientePayload = {
  nome: '', grupo: null, cgc: null, cpf: null, endereco: null, numero: null, complemento: null,
  bairro: null, municipio: null, estado: null, cep: null, contato: null, email: null, telefones: null,
  celular: null, whatsapp: null, whatsapp1: null, whatsapp2: null, insc_mun: null, insc_est: null,
  obs: null, ativo: true,
}

function Harness({ inicial, onSet }: { inicial?: Partial<ClientePayload>; onSet?: (chave: keyof ClientePayload, valor: unknown) => void }) {
  const [form, setForm] = useState<ClientePayload>({ ...VAZIO, ...inicial })
  function set<K extends keyof ClientePayload>(chave: K, valor: ClientePayload[K]) {
    onSet?.(chave, valor)
    setForm((f) => ({ ...f, [chave]: valor }))
  }
  return (
    <ClienteFormFields
      form={form}
      set={set}
      grupos={[]}
      readOnly={false}
      podeEditar
      enviando={false}
      labelSubmit="Salvar"
      onSubmit={(e) => e.preventDefault()}
    />
  )
}

describe('ClienteFormFields', () => {
  it('mascara o CNPJ digitado/colado e guarda so digitos no estado', () => {
    const onSet = vi.fn()
    render(<Harness onSet={onSet} />)
    const input = screen.getByLabelText('CNPJ') as HTMLInputElement
    fireEvent.change(input, { target: { value: '36.312.056/0005-52' } })
    expect(input.value).toBe('36.312.056/0005-52')
    expect(onSet).toHaveBeenCalledWith('cgc', '36312056000552')
  })

  it('mascara o CPF digitado/colado e guarda so digitos no estado', () => {
    const onSet = vi.fn()
    render(<Harness onSet={onSet} />)
    const input = screen.getByLabelText('CPF') as HTMLInputElement
    fireEvent.change(input, { target: { value: '123.456.789-09' } })
    expect(input.value).toBe('123.456.789-09')
    expect(onSet).toHaveBeenCalledWith('cpf', '12345678909')
  })

  it('exibe o CNPJ ja salvo (digitos) mascarado ao editar cliente existente', () => {
    render(<Harness inicial={{ cgc: '36312056000552' }} />)
    expect((screen.getByLabelText('CNPJ') as HTMLInputElement).value).toBe('36.312.056/0005-52')
  })

  it('limpar o campo CNPJ guarda null no estado', () => {
    const onSet = vi.fn()
    render(<Harness inicial={{ cgc: '36312056000552' }} onSet={onSet} />)
    const input = screen.getByLabelText('CNPJ') as HTMLInputElement
    fireEvent.change(input, { target: { value: '' } })
    expect(onSet).toHaveBeenCalledWith('cgc', null)
  })
})
