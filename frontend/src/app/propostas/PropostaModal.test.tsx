import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ user: { id: 1, nome: 'Erick Santos', email: 'erick@hs.com', funcao_id: 1, funcao: 'Administrador' } }),
}))

// react-quill-new nao roda bem em jsdom (Range/getSelection); mockamos o
// wrapper por um textarea simples controlado, suficiente para testar o fluxo
// de dados (value/onChange) sem depender do editor real.
vi.mock('../../components/ui/RichText', () => ({
  RichText: ({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
    <textarea aria-label="Outros itens ou serviços" value={value} onChange={(e) => onChange(e.target.value)} />
  ),
}))

const clientesListar = vi.fn()
const clientesObter = vi.fn()
vi.mock('../clientes/api', () => ({
  clientesApi: {
    listar: (...a: unknown[]) => clientesListar(...a),
    obter: (...a: unknown[]) => clientesObter(...a),
  },
}))

const frotaDoClienteMock = vi.fn()
const servicosListar = vi.fn()
const produtosListar = vi.fn()
const propostasCriar = vi.fn()
const propostasObter = vi.fn()
const propostasAtualizar = vi.fn()

vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return {
    ...real,
    frotaDoCliente: (...a: unknown[]) => frotaDoClienteMock(...a),
    servicosApi: { ...real.servicosApi, listar: (...a: unknown[]) => servicosListar(...a) },
    produtosApi: { ...real.produtosApi, listar: (...a: unknown[]) => produtosListar(...a) },
    propostasApi: {
      ...real.propostasApi,
      criar: (...a: unknown[]) => propostasCriar(...a),
      obter: (...a: unknown[]) => propostasObter(...a),
      atualizar: (...a: unknown[]) => propostasAtualizar(...a),
    },
  }
})

import { PropostaModal } from './PropostaModal'

const CLIENTE = { id: 5, nome: 'Cliente Teste', cgc: '11.111.111/0001-11', cpf: null, municipio: 'Recife', estado: 'PE', ativo: true }
const CLIENTE_COMPLETO = {
  id: 5, grupo: null, nome: 'Cliente Teste', cgc: '11.111.111/0001-11', cpf: null, endereco: 'Rua X, 10',
  numero: null, complemento: null, bairro: null, municipio: 'Recife', estado: 'PE', cep: null, contato: null,
  email: 'cliente@teste.com', telefones: '8130001111', celular: null, whatsapp: null, whatsapp1: null, whatsapp2: null,
  insc_mun: null, insc_est: null, datcad: null, obs: null, ativo: true,
}
const APARELHO_COMUM = {
  id: 42, cliente: 5, cliente_nome: 'Cliente Teste', equipamento: 1, equipamento_descricao: 'Bafômetro X',
  serie: 'SN-001', patrimonio: null, prox_calibragem: null, ativo: true, status: 'A', status_calibracao: 'em_dia',
}
const APARELHO_PHOEBUS = {
  id: 43, cliente: 5, cliente_nome: 'Cliente Teste', equipamento: 2, equipamento_descricao: 'Phoebus 3000',
  serie: 'PH-777', patrimonio: null, prox_calibragem: null, ativo: true, status: 'A', status_calibracao: 'vencido',
}

beforeEach(() => {
  vi.clearAllMocks()
  clientesListar.mockResolvedValue({ items: [CLIENTE], total: 1 })
  clientesObter.mockResolvedValue(CLIENTE_COMPLETO)
  frotaDoClienteMock.mockResolvedValue([APARELHO_COMUM, APARELHO_PHOEBUS])
  servicosListar.mockResolvedValue([])
  produtosListar.mockResolvedValue([])
  propostasCriar.mockResolvedValue({ id: 900 })
})

async function selecionarCliente() {
  fireEvent.change(screen.getByPlaceholderText('Buscar cliente por nome, CNPJ ou CPF'), { target: { value: 'Cliente' } })
  const opcao = await screen.findByText('Cliente Teste')
  fireEvent.click(opcao)
  await screen.findByLabelText('Bafômetro X')
}

describe('PropostaModal', () => {
  it('marcar um aparelho da frota inclui no payload ao submeter', async () => {
    const onSalvo = vi.fn()
    render(<PropostaModal onClose={vi.fn()} onSalvo={onSalvo} />)
    await selecionarCliente()

    fireEvent.click(screen.getByLabelText('Bafômetro X'))
    fireEvent.click(screen.getByText('Criar Proposta'))

    await waitFor(() => expect(propostasCriar).toHaveBeenCalled())
    const payload = propostasCriar.mock.calls[0][0]
    expect(payload.aparelhos).toEqual([{ equipamento_cliente: 42 }])
    expect(onSalvo).toHaveBeenCalledWith(900)
  })

  it('modelo Phoebus preenche o editor de outros itens', async () => {
    render(<PropostaModal onClose={vi.fn()} />)
    await selecionarCliente()

    fireEvent.click(screen.getByLabelText('Phoebus 3000'))
    fireEvent.change(screen.getByLabelText('Modelo do texto'), { target: { value: 'phoebus' } })
    fireEvent.click(screen.getByText('Aplicar modelo'))

    const editor = screen.getByLabelText('Outros itens ou serviços') as HTMLTextAreaElement
    await waitFor(() => expect(editor.value).toContain('Calibração Anual e Anuidade da Plataforma do Aparelho Phoebus'))
    expect(editor.value).toContain('PH-777')
  })

  it('recalcula o total ao adicionar item e informar frete/desconto', async () => {
    render(<PropostaModal onClose={vi.fn()} />)
    await waitFor(() => expect(servicosListar).toHaveBeenCalled())

    fireEvent.click(screen.getByText('Adicionar item'))
    const tabela = screen.getByTestId('tabela-itens')
    const numeros = within(tabela).getAllByRole('spinbutton')
    fireEvent.change(numeros[0], { target: { value: '2' } })
    fireEvent.change(numeros[1], { target: { value: '100' } })
    expect(screen.getByTestId('total-itens').textContent).toContain('200,00')

    fireEvent.change(screen.getByLabelText('Frete (R$)'), { target: { value: '50' } })
    fireEvent.change(screen.getByLabelText('Desconto (R$)'), { target: { value: '20' } })
    expect(screen.getByTestId('total-proposta').textContent).toContain('230,00')
  })

  it('digitar na descricao filtra o catalogo e selecionar um resultado preenche a linha', async () => {
    servicosListar.mockResolvedValue([{ id: 1, nome: 'Calibração Padrão', sku: 'SRV-1', preco: 150 }])
    produtosListar.mockResolvedValue([{ id: 2, nome: 'Bocal Descartável', sku: 'PRD-9', preco: 3.5 }])
    render(<PropostaModal onClose={vi.fn()} />)
    await waitFor(() => expect(servicosListar).toHaveBeenCalled())

    fireEvent.click(screen.getByText('Adicionar item'))
    const descricaoInput = screen.getByPlaceholderText('Digite para buscar no catálogo…')

    fireEvent.change(descricaoInput, { target: { value: 'calibra' } })
    const resultado = await screen.findByText('Calibração Padrão')
    expect(screen.queryByText('Bocal Descartável')).not.toBeInTheDocument()

    fireEvent.click(resultado)

    await waitFor(() => expect((descricaoInput as HTMLInputElement).value).toBe('Calibração Padrão'))
    const tabela = screen.getByTestId('tabela-itens')
    expect(within(tabela).getByDisplayValue('SRV-1')).toBeInTheDocument()
    expect(within(tabela).getByDisplayValue('150')).toBeInTheDocument()
    expect(screen.queryByText('Nenhum resultado no catálogo')).not.toBeInTheDocument()
  })
})
