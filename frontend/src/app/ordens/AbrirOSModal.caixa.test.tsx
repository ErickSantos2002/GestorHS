import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ user: { funcao: 'Expedição' } }),
}))

const { abrir, listarCaixas, criarCaixa } = vi.hoisted(() => ({
  abrir: vi.fn(), listarCaixas: vi.fn(), criarCaixa: vi.fn(),
}))
vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return { ...real, ordensApi: { ...real.ordensApi, abrir } }
})
vi.mock('../caixas/api', async (orig) => {
  const real = await orig<typeof import('../caixas/api')>()
  return { ...real, caixasApi: { ...real.caixasApi, listar: listarCaixas, criar: criarCaixa } }
})
vi.mock('../../lib/recebimento', async (orig) => orig())

import { AbrirOSModal } from './AbrirOSModal'

function tela(props: Record<string, unknown> = {}) {
  return render(
    <MemoryRouter>
      <AbrirOSModal equipamentoClienteId={42} osAtual={null} onClose={vi.fn()} onAberta={vi.fn()} {...props} />
    </MemoryRouter>,
  )
}

const ROTULO = /iniciar em uma caixa existente/i

// Por que a caixa nasce junto com a OS: o número da caixa é o id, então criar
// antes por outra tela era adivinhar qual seria o próximo; e caixa criada num
// passo separado sobrevive à desistência no meio do cadastro, virando caixa vazia.
describe('AbrirOSModal — escolha da caixa', () => {
  beforeEach(() => {
    abrir.mockReset(); listarCaixas.mockReset(); criarCaixa.mockReset()
    abrir.mockResolvedValue({ id: 900, caixa: 77 })
    listarCaixas.mockResolvedValue({ items: [{ id: 77, obs: 'lote', total_os: 2 }], total: 1 })
  })

  it('a opção nasce DESMARCADA e o campo de busca não aparece', async () => {
    tela()
    const marca = await screen.findByLabelText(ROTULO)
    expect((marca as HTMLInputElement).checked).toBe(false)
    expect(screen.queryByPlaceholderText(/Buscar por n/i)).not.toBeInTheDocument()
  })

  it('desmarcada, envia caixa nula — o backend cria a caixa junto', async () => {
    tela()
    await screen.findByLabelText(ROTULO)
    await userEvent.click(screen.getByRole('button', { name: 'Abrir OS' }))

    await waitFor(() => expect(abrir).toHaveBeenCalled())
    expect(abrir.mock.calls[0][0].caixa).toBeNull()
  })

  it('desmarcada, o botão de abrir NÃO fica travado por falta de caixa', async () => {
    // Antes a caixa era obrigatória e o botão ficava desabilitado até escolher uma.
    tela()
    await screen.findByLabelText(ROTULO)
    expect(screen.getByRole('button', { name: 'Abrir OS' })).not.toBeDisabled()
  })

  it('marcada, mostra a busca e exige escolher antes de abrir', async () => {
    tela()
    await userEvent.click(await screen.findByLabelText(ROTULO))

    expect(screen.getByPlaceholderText(/Buscar por n/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Abrir OS' })).toBeDisabled()
  })

  it('marcada e com caixa escolhida, envia o id da caixa', async () => {
    tela()
    await userEvent.click(await screen.findByLabelText(ROTULO))
    fireEvent.change(screen.getByPlaceholderText(/Buscar por n/i), { target: { value: 'lote' } })
    await userEvent.click(await screen.findByText('#77'))
    await userEvent.click(screen.getByRole('button', { name: 'Abrir OS' }))

    await waitFor(() => expect(abrir).toHaveBeenCalled())
    expect(abrir.mock.calls[0][0].caixa).toBe(77)
  })

  it('desmarcar depois de escolher volta a mandar caixa nula', async () => {
    // Senão a escolha ficaria "presa" e o usuário abriria numa caixa que achava
    // ter descartado.
    tela()
    await userEvent.click(await screen.findByLabelText(ROTULO))
    fireEvent.change(screen.getByPlaceholderText(/Buscar por n/i), { target: { value: 'lote' } })
    await userEvent.click(await screen.findByText('#77'))

    await userEvent.click(screen.getByLabelText(ROTULO))
    await userEvent.click(screen.getByRole('button', { name: 'Abrir OS' }))

    await waitFor(() => expect(abrir).toHaveBeenCalled())
    expect(abrir.mock.calls[0][0].caixa).toBeNull()
  })

  it('aberta a partir de uma caixa, a opção nem aparece', async () => {
    // A tela da caixa já abre a OS dentro dela; não há escolha a fazer.
    tela({ caixa: 55 })
    expect(await screen.findByText(/Caixa #55/)).toBeInTheDocument()
    expect(screen.queryByLabelText(ROTULO)).not.toBeInTheDocument()
  })

  it('não dá para criar caixa por aqui', async () => {
    // Criar a caixa neste modal era o ultimo caminho que sobrava para gerar
    // caixa vazia: bastava criar e desistir do resto do cadastro. Sem caixa
    // marcada, o backend cria uma JUNTO com a OS, no mesmo commit.
    tela()
    await userEvent.click(await screen.findByLabelText(ROTULO))
    fireEvent.change(screen.getByPlaceholderText(/Buscar por n/i), { target: { value: '999' } })

    await waitFor(() => expect(listarCaixas).toHaveBeenCalled())
    expect(screen.queryByText(/Criar caixa/i)).not.toBeInTheDocument()
    expect(criarCaixa).not.toHaveBeenCalled()
  })
})
