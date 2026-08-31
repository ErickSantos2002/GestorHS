import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const login = vi.fn()
const apiJson = vi.fn()

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ login, definirSenha: vi.fn(), user: null, loading: false }),
}))

vi.mock('../../lib/api', async () => {
  const real = await vi.importActual<typeof import('../../lib/api')>('../../lib/api')
  return { ...real, apiJson: (...args: unknown[]) => apiJson(...args), apiUrl: (p: string) => `http://api.teste${p}` }
})

import { LoginPage } from './LoginPage'

function montar(query = '') {
  return render(
    <MemoryRouter initialEntries={[`/login${query}`]}>
      <LoginPage />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  apiJson.mockResolvedValue({ ativo: true })
})

describe('LoginPage — SSO', () => {
  it('mostra o botão da Microsoft como âncora para o backend', async () => {
    montar()
    const botao = await screen.findByText('Entrar com Microsoft')
    expect(botao.closest('a')).toHaveAttribute('href', 'http://api.teste/auth/microsoft')
  })

  it('esconde o botão quando o SSO está desligado', async () => {
    apiJson.mockResolvedValue({ ativo: false })
    montar()
    await waitFor(() => expect(apiJson).toHaveBeenCalledWith('/auth/sso/status'))
    expect(screen.queryByText('Entrar com Microsoft')).toBeNull()
  })

  it('esconde o botão se o status falhar', async () => {
    apiJson.mockRejectedValue(new Error('sem rede'))
    montar()
    await waitFor(() => expect(apiJson).toHaveBeenCalled())
    expect(screen.queryByText('Entrar com Microsoft')).toBeNull()
  })

  it('mostra a mensagem de usuário não encontrado vinda do callback', async () => {
    montar('?erro=usuario_nao_encontrado')
    expect(
      await screen.findByText(/Nenhuma conta GestorHS para este e-mail Microsoft/),
    ).toBeInTheDocument()
  })

  it('mostra a mensagem de usuário inativo', async () => {
    montar('?erro=usuario_inativo')
    expect(await screen.findByText(/Usuário desativado/)).toBeInTheDocument()
  })

  it('mostra a mensagem de falha_microsoft — o mais comum dos três, já que 5 ramos do callback caem nele', async () => {
    montar('?erro=falha_microsoft')
    expect(
      await screen.findByText(/Falha na autenticação com a Microsoft/),
    ).toBeInTheDocument()
  })

  it('ignora ?erro= desconhecido', async () => {
    montar('?erro=chute')
    await waitFor(() => expect(apiJson).toHaveBeenCalled())
    expect(screen.getByText('Entrar')).toBeInTheDocument()
  })
})
