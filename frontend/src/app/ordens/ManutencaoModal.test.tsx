import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const { obter, salvar, listarServicos } = vi.hoisted(() => ({
  obter: vi.fn(), salvar: vi.fn(), listarServicos: vi.fn(),
}))
vi.mock('./manutencao', async (orig) => {
  const real = await orig<typeof import('./manutencao')>()
  return { ...real, manutencaoApi: { ...real.manutencaoApi, obter, salvar, listarServicos } }
})

import { ManutencaoModal } from './ManutencaoModal'

const SERVICOS = [
  { id: 1, descricao: 'Troca da placa mãe', resumo_padrao: 'Placa substituída.', ativo: true },
  { id: 2, descricao: 'Troca da bateria', resumo_padrao: 'Bateria trocada.', ativo: true },
  { id: 3, descricao: 'Serviço aposentado', resumo_padrao: 'x.', ativo: false },
]

describe('ManutencaoModal', () => {
  beforeEach(() => {
    obter.mockReset(); salvar.mockReset(); listarServicos.mockReset()
    listarServicos.mockResolvedValue(SERVICOS)
    obter.mockRejectedValue(new Error('404'))   // OS ainda sem manutenção
    salvar.mockResolvedValue({ id: 1, os: 7, numero: 'HF1', data_manutencao: null, resumo: '', servicos: [] })
  })

  it('serviço inativo não aparece para escolher', async () => {
    render(<ManutencaoModal osId={7} onClose={vi.fn()} onSalvo={vi.fn()} />)
    expect(await screen.findByLabelText('Troca da placa mãe')).toBeInTheDocument()
    expect(screen.queryByLabelText('Serviço aposentado')).not.toBeInTheDocument()
  })

  it('escolher serviços compõe o resumo automaticamente', async () => {
    render(<ManutencaoModal osId={7} onClose={vi.fn()} onSalvo={vi.fn()} />)
    await userEvent.click(await screen.findByLabelText('Troca da placa mãe'))
    await userEvent.click(screen.getByLabelText('Troca da bateria'))

    const resumo = screen.getByLabelText('Resumo do serviço') as HTMLTextAreaElement
    await waitFor(() => expect(resumo.value).toBe('Placa substituída. Bateria trocada.'))
  })

  it('depois de editar o resumo, mudar os serviços nao sobrescreve o texto', async () => {
    // Sem essa regra, acrescentar um servico no fim apagaria um texto trabalhado.
    render(<ManutencaoModal osId={7} onClose={vi.fn()} onSalvo={vi.fn()} />)
    await userEvent.click(await screen.findByLabelText('Troca da placa mãe'))
    const resumo = screen.getByLabelText('Resumo do serviço') as HTMLTextAreaElement
    await waitFor(() => expect(resumo.value).toBe('Placa substituída.'))

    fireEvent.change(resumo, { target: { value: 'Texto escrito à mão.' } })
    await userEvent.click(screen.getByLabelText('Troca da bateria'))

    expect(resumo.value).toBe('Texto escrito à mão.')
    expect(screen.getByText(/não acompanha mais os serviços/i)).toBeInTheDocument()
  })

  it('salvar envia número, data, serviços na ordem e resumo', async () => {
    const onSalvo = vi.fn()
    render(<ManutencaoModal osId={7} onClose={vi.fn()} onSalvo={onSalvo} />)
    await userEvent.click(await screen.findByLabelText('Troca da bateria'))
    await userEvent.click(screen.getByLabelText('Troca da placa mãe'))
    fireEvent.change(screen.getByLabelText('Número do relatório'), { target: { value: 'HF00715' } })
    fireEvent.change(screen.getByLabelText('Data da manutenção'), { target: { value: '2026-08-21' } })

    await userEvent.click(screen.getByText('Salvar manutenção'))

    await waitFor(() => expect(salvar).toHaveBeenCalled())
    expect(salvar.mock.calls[0][1]).toEqual({
      numero: 'HF00715',
      data_manutencao: '2026-08-21',
      resumo: 'Bateria trocada. Placa substituída.',
      servicos: [2, 1],
    })
    expect(onSalvo).toHaveBeenCalled()
  })

  it('reabrir com resumo salvo igual a composicao continua acompanhando os servicos', async () => {
    obter.mockReset()
    obter.mockResolvedValue({
      id: 1, os: 7, numero: 'HF1', data_manutencao: null,
      resumo: 'Placa substituída.',
      servicos: [{ servico: 1, descricao: 'Troca da placa mãe', resumo_padrao: 'Placa substituída.' }],
    })
    render(<ManutencaoModal osId={7} onClose={vi.fn()} onSalvo={vi.fn()} />)
    const resumo = await screen.findByLabelText('Resumo do serviço') as HTMLTextAreaElement
    await waitFor(() => expect(resumo.value).toBe('Placa substituída.'))

    await userEvent.click(screen.getByLabelText('Troca da bateria'))

    await waitFor(() => expect(resumo.value).toBe('Placa substituída. Bateria trocada.'))
    expect(screen.queryByText(/não acompanha mais os serviços/i)).not.toBeInTheDocument()
  })

  it('reabrir com resumo salvo editado a mao continua congelado', async () => {
    obter.mockReset()
    obter.mockResolvedValue({
      id: 1, os: 7, numero: 'HF1', data_manutencao: null,
      resumo: 'Texto escrito à mão na vez anterior.',
      servicos: [{ servico: 1, descricao: 'Troca da placa mãe', resumo_padrao: 'Placa substituída.' }],
    })
    render(<ManutencaoModal osId={7} onClose={vi.fn()} onSalvo={vi.fn()} />)
    const resumo = await screen.findByLabelText('Resumo do serviço') as HTMLTextAreaElement
    await waitFor(() => expect(resumo.value).toBe('Texto escrito à mão na vez anterior.'))

    await userEvent.click(screen.getByLabelText('Troca da bateria'))

    expect(resumo.value).toBe('Texto escrito à mão na vez anterior.')
    expect(screen.getByText(/não acompanha mais os serviços/i)).toBeInTheDocument()
  })

  it('sem serviço escolhido nao deixa salvar', async () => {
    render(<ManutencaoModal osId={7} onClose={vi.fn()} onSalvo={vi.fn()} />)
    await screen.findByLabelText('Troca da placa mãe')
    fireEvent.change(screen.getByLabelText('Número do relatório'), { target: { value: 'HF00715' } })
    fireEvent.change(screen.getByLabelText('Data da manutenção'), { target: { value: '2026-08-21' } })
    await userEvent.click(screen.getByText('Salvar manutenção'))
    expect(await screen.findByText(/escolha ao menos um serviço/i)).toBeInTheDocument()
    expect(salvar).not.toHaveBeenCalled()
  })

  // Sem numero e data o relatorio sai com os dois campos em branco — o backend
  // tambem recusa com 409; aqui a recusa chega antes, com mensagem por campo.
  it('sem número nao deixa salvar', async () => {
    render(<ManutencaoModal osId={7} onClose={vi.fn()} onSalvo={vi.fn()} />)
    await userEvent.click(await screen.findByLabelText('Troca da placa mãe'))
    fireEvent.change(screen.getByLabelText('Data da manutenção'), { target: { value: '2026-08-21' } })
    await userEvent.click(screen.getByText('Salvar manutenção'))
    expect(await screen.findByText(/informe o número do relatório/i)).toBeInTheDocument()
    expect(salvar).not.toHaveBeenCalled()
  })

  it('sem data nao deixa salvar', async () => {
    render(<ManutencaoModal osId={7} onClose={vi.fn()} onSalvo={vi.fn()} />)
    await userEvent.click(await screen.findByLabelText('Troca da placa mãe'))
    fireEvent.change(screen.getByLabelText('Número do relatório'), { target: { value: 'HF00715' } })
    await userEvent.click(screen.getByText('Salvar manutenção'))
    expect(await screen.findByText(/informe a data da manutenção/i)).toBeInTheDocument()
    expect(salvar).not.toHaveBeenCalled()
  })
})
