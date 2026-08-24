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

import { ApiError } from '../../lib/api'
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
    obter.mockRejectedValue(new ApiError(404, 'esta OS não tem manutenção registrada'))   // OS ainda sem manutenção
    salvar.mockResolvedValue({ id: 1, os: 7, numero: 'HF1', data_manutencao: null, resumo: '', servicos: [] })
  })

  it('serviço inativo não aparece para escolher', async () => {
    render(<ManutencaoModal osId={7} onClose={vi.fn()} onSalvo={vi.fn()} />)
    expect(await screen.findByLabelText('Troca da placa mãe')).toBeInTheDocument()
    expect(screen.queryByLabelText('Serviço aposentado')).not.toBeInTheDocument()
  })

  // Desativar e' o caminho recomendado para aposentar servico. Escondê-lo de uma
  // manutenção que já o tem grava um serviço sem checkbox: impossível desmarcar,
  // fora do resumo e ainda assim impresso em "Tipo do Problema".
  it('serviço inativo JÁ ESCOLHIDO aparece, marcado como desativado', async () => {
    obter.mockReset()
    obter.mockResolvedValue({
      id: 1, os: 7, numero: 'HF1', data_manutencao: '2026-08-21',
      resumo: 'x.',
      servicos: [{ servico: 3, descricao: 'Serviço aposentado', resumo_padrao: 'x.' }],
    })
    render(<ManutencaoModal osId={7} onClose={vi.fn()} onSalvo={vi.fn()} />)
    const box = await screen.findByLabelText('Serviço aposentado') as HTMLInputElement
    expect(box.checked).toBe(true)
    expect(screen.getByText(/serviço desativado/i)).toBeInTheDocument()
  })

  it('a frase do serviço inativo escolhido continua no resumo composto', async () => {
    obter.mockReset()
    obter.mockResolvedValue({
      id: 1, os: 7, numero: 'HF1', data_manutencao: '2026-08-21',
      resumo: 'x.',
      servicos: [{ servico: 3, descricao: 'Serviço aposentado', resumo_padrao: 'x.' }],
    })
    render(<ManutencaoModal osId={7} onClose={vi.fn()} onSalvo={vi.fn()} />)
    await screen.findByLabelText('Serviço aposentado')
    await userEvent.click(screen.getByLabelText('Troca da bateria'))

    const resumo = screen.getByLabelText('Resumo do serviço') as HTMLTextAreaElement
    await waitFor(() => expect(resumo.value).toBe('x. Bateria trocada.'))
  })

  it('desmarcar o serviço inativo tira ele da manutenção', async () => {
    obter.mockReset()
    obter.mockResolvedValue({
      id: 1, os: 7, numero: 'HF1', data_manutencao: '2026-08-21',
      resumo: 'x.',
      servicos: [{ servico: 3, descricao: 'Serviço aposentado', resumo_padrao: 'x.' }],
    })
    render(<ManutencaoModal osId={7} onClose={vi.fn()} onSalvo={vi.fn()} />)
    await userEvent.click(await screen.findByLabelText('Serviço aposentado'))
    await userEvent.click(screen.getByLabelText('Troca da bateria'))
    await userEvent.click(screen.getByText('Salvar manutenção'))

    await waitFor(() => expect(salvar).toHaveBeenCalled())
    expect(salvar.mock.calls[0][1].servicos).toEqual([2])
    // Desmarcado, some da lista: inativo só continua visível enquanto escolhido.
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

  // O .catch cego tratava 500/queda de rede como "nao ha manutencao": o modal
  // abria vazio e o PUT seguinte apagava numero, data, servicos e o resumo
  // revisado a mao — o unico ponto que anulava o congelamento do resumo.
  it('erro real ao carregar avisa e nao deixa salvar por cima', async () => {
    obter.mockReset()
    obter.mockRejectedValue(new ApiError(500, 'erro interno'))
    render(<ManutencaoModal osId={7} onClose={vi.fn()} onSalvo={vi.fn()} />)
    expect(await screen.findByText(/não foi possível carregar a manutenção já registrada/i)).toBeInTheDocument()

    await userEvent.click(screen.getByLabelText('Troca da placa mãe'))
    fireEvent.change(screen.getByLabelText('Número do relatório'), { target: { value: 'HF00715' } })
    fireEvent.change(screen.getByLabelText('Data da manutenção'), { target: { value: '2026-08-21' } })
    fireEvent.submit(document.getElementById('form-manutencao')!)

    expect(salvar).not.toHaveBeenCalled()
  })

  it('404 ao carregar e o caso normal: modal abre vazio e salva', async () => {
    render(<ManutencaoModal osId={7} onClose={vi.fn()} onSalvo={vi.fn()} />)
    await userEvent.click(await screen.findByLabelText('Troca da placa mãe'))
    fireEvent.change(screen.getByLabelText('Número do relatório'), { target: { value: 'HF00715' } })
    fireEvent.change(screen.getByLabelText('Data da manutenção'), { target: { value: '2026-08-21' } })
    expect(screen.queryByText(/não foi possível carregar/i)).not.toBeInTheDocument()

    await userEvent.click(screen.getByText('Salvar manutenção'))
    await waitFor(() => expect(salvar).toHaveBeenCalled())
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
