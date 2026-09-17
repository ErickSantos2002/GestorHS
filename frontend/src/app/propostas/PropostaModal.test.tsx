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

const destinatariosBuscar = vi.fn()
const empresasObter = vi.fn()
vi.mock('../empresas/api', () => ({
  destinatariosApi: { buscar: (...a: unknown[]) => destinatariosBuscar(...a) },
  empresasApi: { obter: (...a: unknown[]) => empresasObter(...a) },
}))

import { ApiError } from '../../lib/api'
import { PropostaModal } from './PropostaModal'
import { descreverVencimento } from './aparelhosFrota'

const CLIENTE = { id: 5, nome: 'Cliente Teste', cgc: '36312056000552', cpf: null, municipio: 'Recife', estado: 'PE', ativo: true }
const CLIENTE_COMPLETO = {
  id: 5, grupo: null, nome: 'Cliente Teste', cgc: '36312056000552', cpf: null, endereco: 'Rua X, 10',
  numero: null, complemento: null, bairro: null, municipio: 'Recife', estado: 'PE', cep: '50000000', contato: null,
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
  empresa: null, destinatario: null, observacoes: null, assinatura: null, itens: [], aparelhos: [],
  total_itens: 0, total: 0, cliente_nome: 'Cliente Teste', cliente_documento: '36312056000552',
  created_at: null, updated_at: null,
}

const RESULTADO_CLIENTE = { tipo: 'cliente', id: 5, nome: 'Cliente Teste', documento: '36312056000552', municipio: 'Recife', estado: 'PE', matriz_id: null, matriz_nome: null }
const EMPRESA = {
  id: 9, cliente: 5, matriz_nome: 'Cliente Teste', nome: 'Filial Norte', cgc: '11222333000181', cpf: null,
  cep: '29680000', endereco: 'BR 101', numero: 'S/N', complemento: null, bairro: 'Zona Rural',
  municipio: 'Joao Neiva', estado: 'ES', email: 'filial@teste.com', telefone: '2733330000', insc_est: null,
  ativo: true, created_at: null, updated_at: null,
}
const RESULTADO_EMPRESA = { tipo: 'empresa', id: 9, nome: 'Filial Norte', documento: '11222333000181', municipio: 'Joao Neiva', estado: 'ES', matriz_id: 5, matriz_nome: 'Cliente Teste' }

beforeEach(() => {
  vi.clearAllMocks()
  clientesListar.mockResolvedValue({ items: [CLIENTE], total: 1 })
  clientesObter.mockResolvedValue(CLIENTE_COMPLETO)
  frotaDoClienteMock.mockResolvedValue([APARELHO_COMUM, APARELHO_PHOEBUS])
  servicosListar.mockResolvedValue([])
  produtosListar.mockResolvedValue([])
  propostasCriar.mockResolvedValue({ id: 900 })
  destinatariosBuscar.mockResolvedValue([RESULTADO_CLIENTE])
  empresasObter.mockResolvedValue(EMPRESA)
})

const BUSCA = /Buscar cliente ou empresa/

async function selecionarCliente() {
  fireEvent.change(screen.getByPlaceholderText(BUSCA), { target: { value: 'Cliente' } })
  fireEvent.click(await screen.findByRole('button', { name: /Cliente Teste/ }))
  await screen.findByLabelText('Bafômetro X')
}

// "Outros Itens ou Serviços" e obrigatorio para salvar — preenche via modelo.
function aplicarModelo() {
  fireEvent.click(screen.getByText('Aplicar modelo'))
}

// E-mail, telefone e contato nascem SEMPRE vazios (nunca herdam do cadastro) e
// sao obrigatorios, entao todo teste que chega ao submit precisa digitar os
// tres. Usamos os mesmos valores do cadastro; o contato vai para a coluna da
// proposta.
function preencherEmail(valor = 'cliente@teste.com') {
  fireEvent.change(screen.getByLabelText('E-mail *'), { target: { value: valor } })
}

function preencherObrigatorios(email = 'cliente@teste.com') {
  preencherEmail(email)
  fireEvent.change(screen.getByLabelText('Telefone *'), { target: { value: '8130001111' } })
  fireEvent.change(screen.getByLabelText('Contato (aos cuidados de) *'), { target: { value: 'Joana' } })
}

describe('PropostaModal', () => {
  it('marcar um aparelho da frota inclui no payload ao submeter', async () => {
    const onSalvo = vi.fn()
    render(<PropostaModal onClose={vi.fn()} onSalvo={onSalvo} />)

    fireEvent.change(screen.getByPlaceholderText(BUSCA), { target: { value: 'Cliente' } })
    const opcao = await screen.findByRole('button', { name: /Cliente Teste/ })
    expect(screen.getByText(/36\.312\.056\/0005-52/)).toBeInTheDocument()
    expect(screen.queryByText(/36312056000552/)).not.toBeInTheDocument()
    fireEvent.click(opcao)
    await screen.findByLabelText('Bafômetro X')

    expect((screen.getByLabelText(/CNPJ \/ CPF/) as HTMLInputElement).value).toBe('36.312.056/0005-52')

    fireEvent.click(screen.getByLabelText('Bafômetro X'))
    aplicarModelo()
    preencherObrigatorios()
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
    preencherObrigatorios()
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
    preencherObrigatorios()
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

    const busca = screen.getByPlaceholderText(BUSCA)
    fireEvent.change(busca, { target: { value: 'Cliente' } })
    // jsdom nao faz submit implicito; o que garante o comportamento no browser
    // e o preventDefault — fireEvent devolve false quando o evento foi cancelado.
    const naoCancelado = fireEvent.keyDown(busca, { key: 'Enter', code: 'Enter' })

    expect(naoCancelado).toBe(false)
    await waitFor(() => expect(screen.getByText('Cliente Teste')).toBeInTheDocument())
    expect(propostasCriar).not.toHaveBeenCalled()
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
    preencherObrigatorios()

    fireEvent.click(screen.getByText('Criar Proposta'))

    expect(await screen.findByText(/Outros Itens ou Serviços.*Aplicar modelo/i)).toBeInTheDocument()
    expect(propostasCriar).not.toHaveBeenCalled()
  })
})

describe('PropostaModal — destinatario', () => {
  it('cliente escolhido abre os dados preenchidos, documento travado e e-mail vazio com sugestao', async () => {
    render(<PropostaModal onClose={vi.fn()} />)
    await selecionarCliente()
    expect((screen.getByLabelText(/Razão social/) as HTMLInputElement).value).toBe('Cliente Teste')
    expect((screen.getByLabelText(/CNPJ \/ CPF/) as HTMLInputElement).readOnly).toBe(true)
    expect((screen.getByLabelText('E-mail *') as HTMLInputElement).value).toBe('')
    expect(screen.getByRole('button', { name: 'Usar do cadastro: cliente@teste.com' })).toBeInTheDocument()
    expect(screen.getByText(/atualizam o cadastro de Cliente Teste/)).toBeInTheDocument()
  })

  it('salvar envia o destinatario cliente e nao envia cliente nem override', async () => {
    render(<PropostaModal onClose={vi.fn()} />)
    await selecionarCliente()
    fireEvent.change(screen.getByLabelText(/Bairro/), { target: { value: 'Boa Vista' } })
    preencherObrigatorios()
    aplicarModelo()
    fireEvent.click(screen.getByText('Criar Proposta'))
    await waitFor(() => expect(propostasCriar).toHaveBeenCalled())
    const payload = propostasCriar.mock.calls[0][0]
    expect(payload.destinatario).toMatchObject({
      tipo: 'cliente', id: 5, documento: null, bairro: 'Boa Vista', email: 'cliente@teste.com', telefone: '8130001111',
    })
    expect(payload).not.toHaveProperty('cliente')
    expect(payload).not.toHaveProperty('cliente_override')
    expect(payload.contato).toBe('Joana')
  })

  it('empresa escolhida carrega a frota da matriz', async () => {
    destinatariosBuscar.mockResolvedValue([RESULTADO_EMPRESA])
    render(<PropostaModal onClose={vi.fn()} />)
    fireEvent.change(screen.getByPlaceholderText(BUSCA), { target: { value: 'Filial' } })
    fireEvent.click(await screen.findByRole('button', { name: /Filial Norte/ }))
    await screen.findByLabelText('Bafômetro X')
    expect(frotaDoClienteMock).toHaveBeenCalledWith(5)
    expect(screen.getByText('Empresa · matriz Cliente Teste')).toBeInTheDocument()
  })

  it('documento sem resultado cadastra empresa nova com a matriz escolhida', async () => {
    destinatariosBuscar.mockResolvedValue([])
    render(<PropostaModal onClose={vi.fn()} />)
    fireEvent.change(screen.getByPlaceholderText(BUSCA), { target: { value: '11.222.333/0001-81' } })
    fireEvent.click(await screen.findByRole('button', { name: 'Cadastrar empresa com este documento' }))
    expect((screen.getByLabelText(/CNPJ \/ CPF/) as HTMLInputElement).readOnly).toBe(false)
    expect(screen.queryByLabelText('Bafômetro X')).toBeNull()        // sem matriz, sem frota
    fireEvent.change(screen.getByLabelText(/Razão social/), { target: { value: 'Filial Nova' } })
    fireEvent.change(screen.getByLabelText(/^CEP/), { target: { value: '29680000' } })
    fireEvent.change(screen.getByLabelText(/Endereço \*/), { target: { value: 'BR 101' } })
    fireEvent.change(screen.getByLabelText(/Município/), { target: { value: 'Joao Neiva' } })
    fireEvent.change(screen.getByLabelText(/Estado/), { target: { value: 'ES' } })
    preencherObrigatorios()
    aplicarModelo()
    fireEvent.click(screen.getByText('Criar Proposta'))
    await waitFor(() => expect(propostasCriar).toHaveBeenCalled())
    expect(propostasCriar.mock.calls[0][0].destinatario).toMatchObject({
      tipo: 'nova_empresa', id: null, matriz: null, documento: '11222333000181', nome: 'Filial Nova',
    })
  })

  it('409 ao cadastrar empresa oferece usar o cadastro existente', async () => {
    destinatariosBuscar.mockResolvedValueOnce([]).mockResolvedValue([RESULTADO_EMPRESA])
    propostasCriar.mockRejectedValueOnce(new ApiError(409, 'Documento já cadastrado como Empresa: Filial Norte'))
    render(<PropostaModal onClose={vi.fn()} />)
    fireEvent.change(screen.getByPlaceholderText(BUSCA), { target: { value: '11222333000181' } })
    fireEvent.click(await screen.findByRole('button', { name: 'Cadastrar empresa com este documento' }))
    fireEvent.change(screen.getByLabelText(/Razão social/), { target: { value: 'X' } })
    fireEvent.change(screen.getByLabelText(/^CEP/), { target: { value: '29680000' } })
    fireEvent.change(screen.getByLabelText(/Endereço \*/), { target: { value: 'BR 101' } })
    fireEvent.change(screen.getByLabelText(/Município/), { target: { value: 'Joao Neiva' } })
    fireEvent.change(screen.getByLabelText(/Estado/), { target: { value: 'ES' } })
    preencherObrigatorios('filial@teste.com')
    aplicarModelo()
    fireEvent.click(screen.getByText('Criar Proposta'))
    expect(await screen.findByText('Documento já cadastrado como Empresa: Filial Norte')).toBeInTheDocument()
    fireEvent.click(await screen.findByRole('button', { name: 'Usar este cadastro' }))
    await waitFor(() => expect(empresasObter).toHaveBeenCalledWith(9))
    expect(screen.queryByText('Documento já cadastrado como Empresa: Filial Norte')).toBeNull()
    expect((await screen.findByLabelText(/Razão social/) as HTMLInputElement).value).toBe('Filial Norte')
    expect((screen.getByLabelText('E-mail *') as HTMLInputElement).value).toBe('filial@teste.com')   // o digitado fica
  })

  it('trocar destinatario limpa selecao e aparelhos', async () => {
    render(<PropostaModal onClose={vi.fn()} />)
    await selecionarCliente()
    fireEvent.click(screen.getByLabelText('Bafômetro X'))
    fireEvent.click(screen.getByRole('button', { name: 'Trocar destinatário' }))
    expect(screen.getByPlaceholderText(BUSCA)).toBeInTheDocument()
    expect(screen.queryByLabelText('Bafômetro X')).toBeNull()
  })

  it('editar proposta de empresa carrega a empresa atual', async () => {
    propostasObter.mockResolvedValue({ ...PROPOSTA_BASE, empresa: 9, cliente: 5 })
    render(<PropostaModal propostaId={900} onClose={vi.fn()} />)
    expect((await screen.findByLabelText(/Razão social/) as HTMLInputElement).value).toBe('Filial Norte')
    expect(empresasObter).toHaveBeenCalledWith(9)
    expect(clientesObter).not.toHaveBeenCalled()
  })

  it('editar proposta mantem os aparelhos salvos que estao na frota', async () => {
    propostasObter.mockResolvedValue({ ...PROPOSTA_BASE, aparelhos: [{ id: 1, equipamento_cliente: 42 }] })
    propostasAtualizar.mockResolvedValue({ id: 900 })
    render(<PropostaModal propostaId={900} onClose={vi.fn()} />)
    const caixa = (await screen.findByLabelText('Bafômetro X')) as HTMLInputElement
    expect(caixa.checked).toBe(true)
    expect(screen.queryByText(/não estão mais na frota/)).toBeNull()
    aplicarModelo()
    preencherObrigatorios()
    fireEvent.click(screen.getByText('Salvar Alterações'))
    await waitFor(() => expect(propostasAtualizar).toHaveBeenCalled())
    expect(propostasAtualizar.mock.calls[0][1].aparelhos).toEqual([{ equipamento_cliente: 42 }])
  })

  it('falha ao carregar a frota mantem os aparelhos salvos e avisa a falha', async () => {
    // Frota que nao carregou NAO e' frota vazia: retirar os aparelhos aqui
    // apagaria em silencio o que a proposta ja tinha por causa de uma queda de rede.
    propostasObter.mockResolvedValue({ ...PROPOSTA_BASE, aparelhos: [{ id: 1, equipamento_cliente: 42 }] })
    propostasAtualizar.mockResolvedValue({ id: 900 })
    frotaDoClienteMock.mockRejectedValue(new Error('rede'))
    render(<PropostaModal propostaId={900} onClose={vi.fn()} />)
    expect(await screen.findByText(/Não foi possível carregar a frota/)).toBeInTheDocument()
    expect(screen.queryByText(/não estão mais na frota/)).toBeNull()
    aplicarModelo()
    preencherObrigatorios()
    fireEvent.click(screen.getByText('Salvar Alterações'))
    await waitFor(() => expect(propostasAtualizar).toHaveBeenCalled())
    expect(propostasAtualizar.mock.calls[0][1].aparelhos).toEqual([{ equipamento_cliente: 42 }])
  })

  it('aparelho salvo que saiu da frota e retirado da proposta com aviso', async () => {
    propostasObter.mockResolvedValue({
      ...PROPOSTA_BASE, aparelhos: [{ id: 1, equipamento_cliente: 42 }, { id: 2, equipamento_cliente: 77 }],
    })
    propostasAtualizar.mockResolvedValue({ id: 900 })
    render(<PropostaModal propostaId={900} onClose={vi.fn()} />)
    await screen.findByLabelText('Bafômetro X')
    expect(await screen.findByText('1 aparelho(s) não estão mais na frota e foram retirados da proposta.')).toBeInTheDocument()
    aplicarModelo()
    preencherObrigatorios()
    fireEvent.click(screen.getByText('Salvar Alterações'))
    await waitFor(() => expect(propostasAtualizar).toHaveBeenCalled())
    expect(propostasAtualizar.mock.calls[0][1].aparelhos).toEqual([{ equipamento_cliente: 42 }])
  })

  it('empresa sem matriz retira os aparelhos salvos com aviso', async () => {
    propostasObter.mockResolvedValue({ ...PROPOSTA_BASE, empresa: 9, cliente: null, aparelhos: [{ id: 1, equipamento_cliente: 42 }] })
    empresasObter.mockResolvedValue({ ...EMPRESA, cliente: null, matriz_nome: null })
    render(<PropostaModal propostaId={900} onClose={vi.fn()} />)
    expect(await screen.findByText('1 aparelho(s) não estão mais na frota e foram retirados da proposta.')).toBeInTheDocument()
  })

  it('editar proposta de empresa mostra a matriz atual e a manda no payload', async () => {
    propostasObter.mockResolvedValue({ ...PROPOSTA_BASE, empresa: 9, cliente: 5 })
    empresasObter.mockResolvedValue(EMPRESA)
    propostasAtualizar.mockResolvedValue({ id: 900 })
    render(<PropostaModal propostaId={900} onClose={vi.fn()} />)
    await screen.findByText('Cliente matriz (opcional)')
    expect(screen.getByText('Cliente Teste')).toBeInTheDocument()
    aplicarModelo()
    preencherObrigatorios('filial@teste.com')
    fireEvent.click(screen.getByText('Salvar Alterações'))
    await waitFor(() => expect(propostasAtualizar).toHaveBeenCalled())
    expect(propostasAtualizar.mock.calls[0][1].destinatario).toMatchObject({ tipo: 'empresa', id: 9, matriz: 5 })
  })

  it('escolher a matriz de uma empresa sem matriz carrega a frota', async () => {
    propostasObter.mockResolvedValue({ ...PROPOSTA_BASE, empresa: 9, cliente: null })
    empresasObter.mockResolvedValue({ ...EMPRESA, cliente: null, matriz_nome: null })
    render(<PropostaModal propostaId={900} onClose={vi.fn()} />)
    await screen.findByText('Cliente matriz (opcional)')
    expect(frotaDoClienteMock).not.toHaveBeenCalled()
    fireEvent.change(screen.getByPlaceholderText('Buscar cliente por nome, CNPJ ou série do aparelho'), { target: { value: 'Cliente' } })
    fireEvent.click(await screen.findByRole('button', { name: /Cliente Teste/ }))
    await screen.findByLabelText('Bafômetro X')
    expect(frotaDoClienteMock).toHaveBeenCalledWith(5)
    expect(screen.getByText('Empresa · matriz Cliente Teste')).toBeInTheDocument()
  })

  it('submeter sem destinatario nao cria proposta', async () => {
    render(<PropostaModal onClose={vi.fn()} />)
    aplicarModelo()
    fireEvent.click(screen.getByText('Criar Proposta'))
    expect(await screen.findByText('Escolha o destinatário antes de salvar a proposta.')).toBeInTheDocument()
    expect(propostasCriar).not.toHaveBeenCalled()
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
