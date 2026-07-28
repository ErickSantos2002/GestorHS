import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const login = vi.fn()
const definirSenha = vi.fn()

vi.mock('./PortalAuthContext', () => ({
  usePortalAuth: () => ({ login, definirSenha, cliente: null, loading: false }),
}))

import { PortalLoginPage } from './PortalLoginPage'

beforeEach(() => {
  vi.clearAllMocks()
  login.mockResolvedValue({ precisa_redefinir: false })
})

describe('PortalLoginPage', () => {
  it('mascara o documento digitado e envia so digitos ao logar', async () => {
    render(
      <MemoryRouter>
        <PortalLoginPage />
      </MemoryRouter>,
    )
    const input = screen.getByLabelText('CNPJ ou CPF') as HTMLInputElement
    fireEvent.change(input, { target: { value: '36.312.056/0005-52' } })
    expect(input.value).toBe('36.312.056/0005-52')

    fireEvent.change(screen.getByLabelText('Login'), { target: { value: 'usuario1' } })
    fireEvent.change(screen.getByLabelText('Senha'), { target: { value: 'senha123' } })
    fireEvent.click(screen.getByText('Entrar'))

    await waitFor(() => expect(login).toHaveBeenCalledWith('36312056000552', 'usuario1', 'senha123'))
  })

  it('colar um CPF ja formatado tambem normaliza para digitos', async () => {
    render(
      <MemoryRouter>
        <PortalLoginPage />
      </MemoryRouter>,
    )
    const input = screen.getByLabelText('CNPJ ou CPF') as HTMLInputElement
    fireEvent.change(input, { target: { value: '123.456.789-09' } })
    expect(input.value).toBe('123.456.789-09')
    fireEvent.change(screen.getByLabelText('Login'), { target: { value: 'usuario1' } })
    fireEvent.change(screen.getByLabelText('Senha'), { target: { value: 'senha123' } })
    fireEvent.click(screen.getByText('Entrar'))
    await waitFor(() => expect(login).toHaveBeenCalledWith('12345678909', 'usuario1', 'senha123'))
  })
})
