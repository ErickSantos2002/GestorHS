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
import { descreverVencimento } from './aparelhosFrota'

const CLIENTE = { id: 5, nome: 'Cliente Teste', cgc: '36312056000552', cpf: null, municipio: 'Recife', estado: 'PE', ativo: true }
const CLIENTE_COMPLETO = {
  id: 5, grupo: null, nome: 'Cliente Teste', cgc: '36312056000552', cpf: null, endereco: 'Rua X, 10',
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

    fireEvent.change(screen.getByPlaceholderText('Buscar cliente por nome, CNPJ ou CPF'), { target: { value: 'Cliente' } })
    await screen.findByText('Cliente Teste')
    expect(screen.getByText('36.312.056/0005-52')).toBeInTheDocument()
    expect(screen.queryByText('36312056000552')).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('Cliente Teste'))
    await screen.findByLabelText('Bafômetro X')

    expect(screen.getByText('CNPJ/CPF: 36.312.056/0005-52')).toBeInTheDocument()

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

  it('busca de aparelhos filtra a lista da frota sem desmarcar selecionados', async () => {
    render(<PropostaModal onClose={vi.fn()} />)
    await selecionarCliente()
    await screen.findByLabelText('Phoebus 3000')

    fireEvent.click(screen.getByLabelText('Bafômetro X'))

    fireEvent.change(screen.getByPlaceholderText('Buscar aparelho por descrição ou série'), { target: { value: 'phoebus' } })
    expect(screen.queryByLabelText('Bafômetro X')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Phoebus 3000')).toBeInTheDocument()

    fireEvent.click(screen.getByText('Criar Proposta'))
    await waitFor(() => expect(propostasCriar).toHaveBeenCalled())
    const payload = propostasCriar.mock.calls[0][0]
    expect(payload.aparelhos).toEqual([{ equipamento_cliente: 42 }])
  })

  it('digitar na Introdução envia o texto no payload ao submeter', async () => {
    render(<PropostaModal onClose={vi.fn()} />)
    await selecionarCliente()

    fireEvent.change(screen.getByLabelText(/introdução/i), { target: { value: 'Texto de introdução digitado.' } })
    fireEvent.click(screen.getByText('Criar Proposta'))

    await waitFor(() => expect(propostasCriar).toHaveBeenCalled())
    const payload = propostasCriar.mock.calls[0][0]
    expect(payload.intro).toBe('Texto de introdução digitado.')
  })

  it('ao editar uma proposta existente, o campo Introdução vem pré-preenchido', async () => {
    propostasObter.mockResolvedValue({
      id: 900,
      numero: 10,
      cliente: 5,
      contato: null,
      vendedor: 'Erick Santos',
      data: '2026-07-24',
      intro: 'Endereço Confirmado.',
      outros_itens: null,
      desconto: 0,
      frete: 0,
      forma_envio: null,
      forma_frete: null,
      transportador: null,
      condicao_pagamento: null,
      validade_dias: 30,
      data_entrega: null,
      descricao_entrega: null,
      endereco_entrega_diferente: false,
      endereco_entrega: null,
      cliente_override: null,
      observacoes: null,
      assinatura: null,
      itens: [],
      aparelhos: [],
      total_itens: 0,
      total: 0,
      cliente_nome: 'Cliente Teste',
      cliente_documento: '36312056000552',
      created_at: null,
      updated_at: null,
    })

    render(<PropostaModal propostaId={900} onClose={vi.fn()} />)

    const campo = (await screen.findByLabelText(/introdução/i)) as HTMLTextAreaElement
    expect(campo.value).toBe('Endereço Confirmado.')
  })

  it('override de documento nasce mascarado com o CNPJ do cadastro e guarda so digitos', async () => {
    render(<PropostaModal onClose={vi.fn()} />)
    await selecionarCliente()

    fireEvent.click(screen.getByLabelText('Editar dados nesta proposta'))
    const documentoInput = screen.getByLabelText('CNPJ / Documento') as HTMLInputElement
    expect(documentoInput.value).toBe('36.312.056/0005-52')

    fireEvent.change(documentoInput, { target: { value: '123.456.789-09' } })
    expect(documentoInput.value).toBe('123.456.789-09')

    fireEvent.click(screen.getByText('Aplicar'))
    fireEvent.click(screen.getByText('Criar Proposta'))

    await waitFor(() => expect(propostasCriar).toHaveBeenCalled())
    const payload = propostasCriar.mock.calls[0][0]
    expect(payload.cliente_override.documento).toBe('12345678909')
  })
})

describe('descreverVencimento', () => {
  const hoje = new Date(2026, 6, 24) // 24/07/2026 (mes 0-indexado)

  it('sem data retorna aviso de sem data', () => {
    expect(descreverVencimento(null, hoje)).toContain('Sem data')
  })

  it('data futura distante mostra meses restantes', () => {
    const texto = descreverVencimento('2026-11-24', hoje)
    expect(texto).toContain('faltam')
    expect(texto).toContain('meses')
  })

  it('data futura proxima (menos de 2 meses) mostra dias restantes', () => {
    const texto = descreverVencimento('2026-08-05', hoje)
    expect(texto).toContain('faltam')
    expect(texto).toContain('dias')
  })

  it('data passada mostra que ja venceu', () => {
    const texto = descreverVencimento('2026-01-10', hoje)
    expect(texto).toMatch(/Venceu|vencido/)
  })
})
