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

const buscarCep = vi.fn()
const buscarCnpj = vi.fn()
vi.mock('./buscaEndereco', async (orig) => {
  const real = await orig<typeof import('./buscaEndereco')>()
  return { ...real, buscaApi: { cep: (...a: unknown[]) => buscarCep(...a), cnpj: (...a: unknown[]) => buscarCnpj(...a) } }
})

import { ApiError } from '../../lib/api'
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

/** Proposta ja salva, do jeito que `propostasApi.obter` devolve. */
const PROPOSTA_BASE = {
  id: 900, numero: 10, cliente: 5, contato: null, vendedor: 'Erick Santos', data: '2026-07-24',
  intro: null, outros_itens: null, desconto: 0, frete: 0, forma_envio: null, forma_frete: null,
  transportador: null, condicao_pagamento: null, validade_dias: 30, data_entrega: null,
  descricao_entrega: null, endereco_entrega_diferente: false, endereco_entrega: null,
  cliente_override: null, observacoes: null, assinatura: null, itens: [], aparelhos: [],
  total_itens: 0, total: 0, cliente_nome: 'Cliente Teste', cliente_documento: '36312056000552',
  created_at: null, updated_at: null,
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

// "Outros Itens ou Serviços" e obrigatorio para salvar — preenche via modelo.
function aplicarModelo() {
  fireEvent.click(screen.getByText('Aplicar modelo'))
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
    aplicarModelo()
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

    aplicarModelo()
    fireEvent.click(screen.getByText('Criar Proposta'))
    await waitFor(() => expect(propostasCriar).toHaveBeenCalled())
    const payload = propostasCriar.mock.calls[0][0]
    expect(payload.aparelhos).toEqual([{ equipamento_cliente: 42 }])
  })

  it('digitar na Introdução envia o texto no payload ao submeter', async () => {
    render(<PropostaModal onClose={vi.fn()} />)
    await selecionarCliente()

    fireEvent.change(screen.getByLabelText(/introdução/i), { target: { value: 'Texto de introdução digitado.' } })
    aplicarModelo()
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

  it('Enter na busca de cliente nao submete o formulario', async () => {
    render(<PropostaModal onClose={vi.fn()} />)
    await waitFor(() => expect(servicosListar).toHaveBeenCalled())

    const busca = screen.getByPlaceholderText('Buscar cliente por nome, CNPJ ou CPF')
    fireEvent.change(busca, { target: { value: 'Cliente' } })
    // jsdom nao faz submit implicito; o que garante o comportamento no browser
    // e o preventDefault — fireEvent devolve false quando o evento foi cancelado.
    const naoCancelado = fireEvent.keyDown(busca, { key: 'Enter', code: 'Enter' })

    expect(naoCancelado).toBe(false)
    await waitFor(() => expect(screen.getByText('Cliente Teste')).toBeInTheDocument())
    expect(propostasCriar).not.toHaveBeenCalled()
  })

  it('submeter sem cliente nao cria proposta e mostra erro', async () => {
    const onSalvo = vi.fn()
    render(<PropostaModal onClose={vi.fn()} onSalvo={onSalvo} />)
    await waitFor(() => expect(servicosListar).toHaveBeenCalled())

    fireEvent.click(screen.getByText('Criar Proposta'))

    expect(await screen.findByText(/selecione o cliente/i)).toBeInTheDocument()
    expect(propostasCriar).not.toHaveBeenCalled()
    expect(onSalvo).not.toHaveBeenCalled()
  })

  it('clique fora nao fecha a proposta; o X fecha', async () => {
    const onClose = vi.fn()
    render(<PropostaModal onClose={onClose} />)
    await waitFor(() => expect(servicosListar).toHaveBeenCalled())

    fireEvent.click(screen.getByTestId('modal-backdrop'))
    expect(onClose).not.toHaveBeenCalled()

    fireEvent.click(screen.getByLabelText('Fechar'))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('submeter sem o bloco de outros itens nao cria proposta', async () => {
    render(<PropostaModal onClose={vi.fn()} />)
    await selecionarCliente()

    fireEvent.click(screen.getByText('Criar Proposta'))

    expect(await screen.findByText(/Outros Itens ou Serviços.*Aplicar modelo/i)).toBeInTheDocument()
    expect(propostasCriar).not.toHaveBeenCalled()
  })

  it('cliente sem CNPJ/CPF no cadastro bloqueia o salvamento ate preencher o override', async () => {
    clientesObter.mockResolvedValue({ ...CLIENTE_COMPLETO, cgc: null, cpf: null })
    render(<PropostaModal onClose={vi.fn()} />)
    await selecionarCliente()
    aplicarModelo()

    expect(await screen.findByText(/não tem CNPJ\/CPF no cadastro/i)).toBeInTheDocument()

    fireEvent.click(screen.getByText('Criar Proposta'))
    expect(await screen.findByText(/nao tem CNPJ\/CPF\. Preencha o documento/i)).toBeInTheDocument()
    expect(propostasCriar).not.toHaveBeenCalled()

    // Preenchendo o documento no override, a proposta passa a poder ser salva.
    fireEvent.click(screen.getByLabelText('Editar dados nesta proposta'))
    fireEvent.change(screen.getByLabelText('CNPJ / Documento'), { target: { value: '36.312.056/0005-52' } })
    fireEvent.click(screen.getByText('Aplicar'))
    fireEvent.click(screen.getByText('Criar Proposta'))

    await waitFor(() => expect(propostasCriar).toHaveBeenCalled())
    expect(propostasCriar.mock.calls[0][0].cliente_override.documento).toBe('36312056000552')
  })

  it('REPRO proposta 99: troca o CNPJ numa proposta que ja tem override e salva', async () => {
    // Dados reais da proposta 99: cliente RUMO (cgc 02502844000166) com override
    // de email/telefone/contato ja gravado. O usuario troca o documento para o
    // CNPJ da filial e salva.
    clientesObter.mockResolvedValue({ ...CLIENTE_COMPLETO, cgc: '02502844000166' })
    propostasObter.mockResolvedValue({
      ...PROPOSTA_BASE,
      outros_itens: '<p>servicos</p>',
      cliente_override: { email: 'Tatiane.kava@rumolog.com', telefone: '+55 41 9710-1221', contato: 'Tatiane' },
    })
    propostasAtualizar.mockResolvedValue({ id: 900 })

    render(<PropostaModal propostaId={900} onClose={vi.fn()} />)
    await screen.findByText(/CNPJ\/CPF:/)
    fireEvent.click(screen.getByLabelText('Editar dados nesta proposta'))

    fireEvent.change(screen.getByLabelText('CNPJ / Documento'), { target: { value: '01.258.944/0005-50' } })

    // Sequencia real: ele clicou na lupa ANTES de aplicar, e a busca falhou.
    buscarCnpj.mockRejectedValue(new ApiError(502, 'servico de consulta indisponivel'))
    fireEvent.click(screen.getByLabelText('Buscar dados pelo CNPJ'))
    await screen.findByText(/indisponível/i)

    fireEvent.click(screen.getByText('Aplicar'))
    fireEvent.click(screen.getByText('Salvar Alterações'))

    await waitFor(() => expect(propostasAtualizar).toHaveBeenCalled())
    const payload = propostasAtualizar.mock.calls[0][1]
    expect(payload.cliente_override.documento).toBe('01258944000550')
    // os campos que ja existiam nao podem sumir na troca
    expect(payload.cliente_override.email).toBe('Tatiane.kava@rumolog.com')
  })

  it('fechar o painel com edicao pendente avisa antes de descartar', async () => {
    // Foi assim que o CNPJ da proposta 99 se perdeu: com o erro da busca logo
    // acima dos botoes, o X e o Cancelar jogavam fora o que tinha sido digitado
    // sem dizer nada, e a proposta salvava com o override antigo.
    const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(false)
    render(<PropostaModal onClose={vi.fn()} />)
    await selecionarCliente()
    fireEvent.click(screen.getByLabelText('Editar dados nesta proposta'))

    fireEvent.change(screen.getByLabelText('CNPJ / Documento'), { target: { value: '01.258.944/0005-50' } })
    fireEvent.click(within(screen.getByTestId('painel-override')).getByText('Cancelar'))

    expect(confirmar).toHaveBeenCalled()
    // Recusou descartar: o painel continua aberto com o que foi digitado.
    expect((screen.getByLabelText('CNPJ / Documento') as HTMLInputElement).value).toBe('01.258.944/0005-50')

    confirmar.mockReturnValue(true)
    fireEvent.click(within(screen.getByTestId('painel-override')).getByText('Cancelar'))
    await waitFor(() => expect(screen.queryByLabelText('CNPJ / Documento')).not.toBeInTheDocument())
    confirmar.mockRestore()
  })

  it('fechar o painel sem ter mudado nada nao pergunta nada', async () => {
    const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(<PropostaModal onClose={vi.fn()} />)
    await selecionarCliente()
    fireEvent.click(screen.getByLabelText('Editar dados nesta proposta'))

    fireEvent.click(within(screen.getByTestId('painel-override')).getByText('Cancelar'))
    expect(confirmar).not.toHaveBeenCalled()
    confirmar.mockRestore()
  })

  it('reabrir uma proposta com override recompoe os campos nao editados a partir do cadastro', async () => {
    // O override guarda SO o que diverge do cadastro. Antes, reabrir mostrava os
    // demais campos EM BRANCO — mesmo o cliente tendo o dado e o PDF imprimindo
    // o do cadastro. Foi o que fez o usuario achar que a edicao nao salvava.
    propostasObter.mockResolvedValue({
      ...PROPOSTA_BASE,
      cliente_override: { email: 'contato@filial.com', telefone: '41999990000', contato: 'Tatiane' },
    })

    render(<PropostaModal propostaId={900} onClose={vi.fn()} />)
    // Espera o CADASTRO do cliente chegar: e' dele que os campos nao editados
    // sao herdados, e o botao do painel aparece antes disso.
    await screen.findByText('CNPJ/CPF: 36.312.056/0005-52')
    fireEvent.click(screen.getByLabelText('Editar dados nesta proposta'))

    // Editado nesta proposta: vem do override.
    expect((screen.getByLabelText('E-mail') as HTMLInputElement).value).toBe('contato@filial.com')
    // Nao editado: vem do cadastro, em vez de aparecer em branco.
    expect((screen.getByLabelText('CNPJ / Documento') as HTMLInputElement).value).toBe('36.312.056/0005-52')
    expect((screen.getByLabelText('Razão social / Nome') as HTMLInputElement).value).toBe('Cliente Teste')
    expect((screen.getByLabelText('Endereço') as HTMLInputElement).value).toBe('Rua X, 10')
  })

  it('campo herdado do cadastro fica marcado; editado perde a marcacao na hora', async () => {
    render(<PropostaModal onClose={vi.fn()} />)
    await selecionarCliente()
    fireEvent.click(screen.getByLabelText('Editar dados nesta proposta'))

    const nome = screen.getByLabelText('Razão social / Nome')
    expect(nome.className).toMatch(/italic/)

    fireEvent.change(nome, { target: { value: 'Filial Recife' } })
    expect(nome.className).not.toMatch(/italic/)
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

    // O override e' aberto pre-preenchido com o cadastro inteiro, mas o aviso
    // deve apontar so o que de fato mudou.
    expect(await screen.findByText(/Editados só nesta proposta: CNPJ \/ Documento\./)).toBeInTheDocument()

    aplicarModelo()
    fireEvent.click(screen.getByText('Criar Proposta'))

    await waitFor(() => expect(propostasCriar).toHaveBeenCalled())
    const payload = propostasCriar.mock.calls[0][0]
    expect(payload.cliente_override.documento).toBe('12345678909')
    // so o campo que divergiu entra no override
    expect(Object.keys(payload.cliente_override)).toEqual(['documento'])
  })

  it('aplicar override sem mudar nada nao grava override', async () => {
    render(<PropostaModal onClose={vi.fn()} />)
    await selecionarCliente()

    fireEvent.click(screen.getByLabelText('Editar dados nesta proposta'))
    fireEvent.click(screen.getByText('Aplicar'))

    // nada divergiu do cadastro: a proposta nao pode ficar marcada como editada
    expect(screen.queryByText(/Editados só nesta proposta/)).not.toBeInTheDocument()

    aplicarModelo()
    fireEvent.click(screen.getByText('Criar Proposta'))
    await waitFor(() => expect(propostasCriar).toHaveBeenCalled())
    expect(propostasCriar.mock.calls[0][0].cliente_override).toBeNull()
  })

  it('proposta antiga com override redundante (8 campos iguais ao cadastro) nao mostra o aviso quebrado', async () => {
    // Simula uma proposta criada antes da mudanca que passou a gravar so os
    // campos divergentes: o override tem os campos preenchidos, mas todos
    // batem com o cadastro atual do cliente — nao sera migrada.
    propostasObter.mockResolvedValue({
      id: 901,
      numero: 11,
      cliente: 5,
      contato: null,
      vendedor: 'Erick Santos',
      data: '2026-07-24',
      intro: '',
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
      cliente_override: {
        nome: 'Cliente Teste',
        documento: '36312056000552',
        endereco: 'Rua X, 10',
        municipio: 'Recife',
        estado: 'PE',
        cep: '',
        email: 'cliente@teste.com',
        telefone: '8130001111',
      },
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

    render(<PropostaModal propostaId={901} onClose={vi.fn()} />)

    await screen.findByText('Cliente Teste')
    // aguarda o cadastro completo do cliente carregar antes de checar o aviso
    await waitFor(() => expect(clientesObter).toHaveBeenCalledWith(5))

    expect(screen.queryByText(/Editados só nesta proposta/)).not.toBeInTheDocument()
  })
})

describe('PropostaModal — busca de CEP e CNPJ', () => {
  const RESULTADO_CNPJ = {
    documento: '36312056000552', nome: 'Acme Industria Ltda', endereco: 'Rua Nova, 10',
    municipio: 'Olinda', estado: 'PE', cep: '53000000', situacao: 'ATIVA',
  }
  const RESULTADO_CEP = {
    cep: '53000000', endereco: 'Rua Nova', municipio: 'Olinda', estado: 'PE',
  }

  async function abrirOverride() {
    render(<PropostaModal onClose={vi.fn()} />)
    await selecionarCliente()
    fireEvent.click(screen.getByLabelText('Editar dados nesta proposta'))
  }

  it('lupa do CNPJ preenche razao social, endereco, municipio, estado e CEP', async () => {
    buscarCnpj.mockResolvedValue(RESULTADO_CNPJ)
    await abrirOverride()

    fireEvent.click(screen.getByLabelText('Buscar dados pelo CNPJ'))

    await waitFor(() => expect(buscarCnpj).toHaveBeenCalledWith('36312056000552'))
    expect((screen.getByLabelText('Razão social / Nome') as HTMLInputElement).value).toBe('Acme Industria Ltda')
    expect((screen.getByLabelText('Endereço') as HTMLInputElement).value).toBe('Rua Nova, 10')
    expect((screen.getByLabelText('Município') as HTMLInputElement).value).toBe('Olinda')
    expect((screen.getByLabelText('CEP') as HTMLInputElement).value).toBe('53000-000')
  })

  it('lupa do CNPJ nao altera telefone nem e-mail', async () => {
    buscarCnpj.mockResolvedValue(RESULTADO_CNPJ)
    await abrirOverride()
    const email = screen.getByLabelText('E-mail') as HTMLInputElement
    const antes = email.value

    fireEvent.click(screen.getByLabelText('Buscar dados pelo CNPJ'))
    await waitFor(() => expect(buscarCnpj).toHaveBeenCalled())

    expect(email.value).toBe(antes)
  })

  it('mostra os campos preenchidos e a situacao cadastral', async () => {
    buscarCnpj.mockResolvedValue(RESULTADO_CNPJ)
    await abrirOverride()

    fireEvent.click(screen.getByLabelText('Buscar dados pelo CNPJ'))

    expect(await screen.findByText(/Preenchido pelo CNPJ:/)).toBeInTheDocument()
    expect(screen.getByText(/Situação na Receita: ATIVA/)).toBeInTheDocument()
  })

  it('Desfazer restaura os valores anteriores a busca', async () => {
    buscarCnpj.mockResolvedValue(RESULTADO_CNPJ)
    await abrirOverride()
    const nome = screen.getByLabelText('Razão social / Nome') as HTMLInputElement
    const antes = nome.value

    fireEvent.click(screen.getByLabelText('Buscar dados pelo CNPJ'))
    await waitFor(() => expect(nome.value).toBe('Acme Industria Ltda'))

    fireEvent.click(screen.getByText('Desfazer'))

    expect(nome.value).toBe(antes)
    expect(screen.queryByText(/Preenchido pelo CNPJ:/)).not.toBeInTheDocument()
  })

  it('o painel abre com o CEP do cadastro ja preenchido', async () => {
    clientesObter.mockResolvedValue({ ...CLIENTE_COMPLETO, cep: '50030230' })
    await abrirOverride()
    expect((screen.getByLabelText('CEP') as HTMLInputElement).value).toBe('50030-230')
  })

  it('lupa do CEP preenche endereco, municipio e estado sem tocar no nome', async () => {
    buscarCep.mockResolvedValue(RESULTADO_CEP)
    await abrirOverride()
    const nome = screen.getByLabelText('Razão social / Nome') as HTMLInputElement
    const antes = nome.value

    fireEvent.change(screen.getByLabelText('CEP'), { target: { value: '53000-000' } })
    fireEvent.click(screen.getByLabelText('Buscar endereço pelo CEP'))

    await waitFor(() => expect(buscarCep).toHaveBeenCalledWith('53000000'))
    expect((screen.getByLabelText('Endereço') as HTMLInputElement).value).toBe('Rua Nova')
    expect(nome.value).toBe(antes)
  })

  it('CNPJ nao encontrado mostra mensagem e nao altera campo nenhum', async () => {
    const { ApiError } = await import('../../lib/api')
    buscarCnpj.mockRejectedValue(new ApiError(404, 'nao encontrado'))
    await abrirOverride()
    const nome = screen.getByLabelText('Razão social / Nome') as HTMLInputElement
    const antes = nome.value

    fireEvent.click(screen.getByLabelText('Buscar dados pelo CNPJ'))

    expect(await screen.findByText(/CNPJ não encontrado/i)).toBeInTheDocument()
    expect(nome.value).toBe(antes)
  })

  it('provedor fora do ar mostra mensagem de indisponivel', async () => {
    const { ApiError } = await import('../../lib/api')
    buscarCep.mockRejectedValue(new ApiError(502, 'fora'))
    await abrirOverride()

    fireEvent.change(screen.getByLabelText('CEP'), { target: { value: '53000-000' } })
    fireEvent.click(screen.getByLabelText('Buscar endereço pelo CEP'))

    expect(await screen.findByText(/indisponível/i)).toBeInTheDocument()
  })

  it('busca em andamento desabilita as duas lupas, evitando que a segunda sobrescreva a primeira', async () => {
    // Promise controlada a mao: so resolve quando o teste mandar, pra segurar
    // a busca de CNPJ "em voo" e tentar disparar a de CEP nesse meio-tempo.
    let resolverCnpj: (r: typeof RESULTADO_CNPJ) => void = () => {}
    const promessaCnpj = new Promise<typeof RESULTADO_CNPJ>((resolve) => { resolverCnpj = resolve })
    buscarCnpj.mockReturnValue(promessaCnpj)
    await abrirOverride()

    fireEvent.click(screen.getByLabelText('Buscar dados pelo CNPJ'))

    await waitFor(() => expect(screen.getByLabelText('Buscar dados pelo CNPJ')).toBeDisabled())
    expect(screen.getByLabelText('Buscar endereço pelo CEP')).toBeDisabled()

    // Enquanto a busca de CNPJ esta em voo, a lupa do CEP esta desabilitada:
    // o clique nao chega ao handler, entao nao ha uma segunda busca concorrente
    // capturando um draft desatualizado e sobrescrevendo o resultado da primeira.
    fireEvent.click(screen.getByLabelText('Buscar endereço pelo CEP'))
    expect(buscarCep).not.toHaveBeenCalled()

    resolverCnpj(RESULTADO_CNPJ)
    await waitFor(() => expect(screen.getByLabelText('Buscar dados pelo CNPJ')).not.toBeDisabled())
    expect(screen.getByLabelText('Buscar endereço pelo CEP')).not.toBeDisabled()
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
