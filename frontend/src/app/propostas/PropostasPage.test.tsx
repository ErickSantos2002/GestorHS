import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

const useAuth = vi.fn()
vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => useAuth(),
}))

// Os modais são pesados (editor rico / fetch de versões) e não são o alvo aqui.
vi.mock('./PropostaModal', () => ({ PropostaModal: () => <div data-testid="proposta-modal" /> }))
vi.mock('./HistoricoModal', () => ({ HistoricoModal: () => <div data-testid="historico-modal" /> }))

const clientesObter = vi.fn()
vi.mock('../clientes/api', () => ({
  clientesApi: { obter: (...a: unknown[]) => clientesObter(...a) },
}))

const listar = vi.fn()
const desabilitar = vi.fn()
const reativar = vi.fn()
const duplicar = vi.fn()
const baixarPdf = vi.fn()
const faturar = vi.fn()
const desfaturar = vi.fn()

vi.mock('./api', async (orig) => {
  const real = await orig<typeof import('./api')>()
  return {
    ...real,
    propostasApi: {
      ...real.propostasApi,
      listar: (...a: unknown[]) => listar(...a),
      desabilitar: (...a: unknown[]) => desabilitar(...a),
      reativar: (...a: unknown[]) => reativar(...a),
      duplicar: (...a: unknown[]) => duplicar(...a),
      baixarPdf: (...a: unknown[]) => baixarPdf(...a),
      faturar: (...a: unknown[]) => faturar(...a),
      desfaturar: (...a: unknown[]) => desfaturar(...a),
    },
  }
})

import { PropostasPage } from './PropostasPage'

const USUARIO_ADMIN = { id: 1, nome: 'Erick', email: 'e@hs.com', funcao_id: 1, funcao: 'Administrador' }
const USUARIO_SEM_ESCRITA = { id: 2, nome: 'Fulano', email: 'f@hs.com', funcao_id: 2, funcao: 'Laboratório' }
const USUARIO_FINANCEIRO = { id: 3, nome: 'Beltrana', email: 'b@hs.com', funcao_id: 3, funcao: 'Financeiro' }

const PROPOSTA = {
  id: 10, numero: 42, data: '2026-07-20', cliente_nome: 'Cliente Teste', cliente_documento: '36312056000552',
  total: 1250.5, total_itens: 1250.5, desconto: 0, frete: 0, itens: [], aparelhos: [],
  cliente: 5, contato: null, vendedor: null, intro: null, outros_itens: null, forma_envio: null, forma_frete: null,
  transportador: null, condicao_pagamento: null, validade_dias: null, data_entrega: null, descricao_entrega: null,
  endereco_entrega_diferente: false, endereco_entrega: null, cliente_override: null, observacoes: null, assinatura: null,
  created_at: null, updated_at: null,
  faturada: false, faturada_em: null, faturada_por: null,
  is_deleted: false, deleted_at: null,
}

// jsdom não implementa URL.createObjectURL/revokeObjectURL — atribuímos stubs
// para o arquivo todo (o unmount da modal de Visualizar chama revoke no
// cleanup do RTL, que roda depois do corpo do teste, então restaurar dentro
// do `it` seria cedo demais).
URL.createObjectURL = vi.fn().mockReturnValue('blob:mock')
URL.revokeObjectURL = vi.fn()

const CLIENTE_CADASTRO = {
  id: 5, grupo: null, nome: 'Cliente Teste', cgc: '36312056000552', cpf: null, endereco: 'Rua X, 10',
  numero: null, complemento: null, bairro: null, municipio: 'Recife', estado: 'PE', cep: null, contato: 'Ana',
  email: 'cliente@teste.com', telefones: '8130001111', celular: null, whatsapp: null, whatsapp1: null, whatsapp2: null,
  insc_mun: null, insc_est: null, datcad: null, obs: null, ativo: true,
}

beforeEach(() => {
  vi.clearAllMocks()
  useAuth.mockReturnValue({ user: USUARIO_ADMIN })
  listar.mockResolvedValue({ items: [PROPOSTA], total: 1, page: 1, page_size: 25, total_pages: 1 })
  desabilitar.mockResolvedValue({ ...PROPOSTA, is_deleted: true })
  reativar.mockResolvedValue({ ...PROPOSTA, is_deleted: false })
  clientesObter.mockResolvedValue(CLIENTE_CADASTRO)
})

describe('PropostasPage', () => {
  it('renderiza a lista com linha e ações em ícone (usuário com escrita)', async () => {
    render(<PropostasPage />)
    expect(await screen.findByText('#42')).toBeInTheDocument()
    expect(screen.getByText('Cliente Teste')).toBeInTheDocument()
    expect(screen.getByText('36.312.056/0005-52')).toBeInTheDocument()
    expect(screen.getByText('R$ 1.250,50')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /visualizar/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /baixar pdf/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /histórico/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /editar/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /duplicar/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /desabilitar/i })).toBeInTheDocument()
  })

  it('esconde as ações de escrita para usuário sem permissão', async () => {
    useAuth.mockReturnValue({ user: USUARIO_SEM_ESCRITA })
    render(<PropostasPage />)
    await screen.findByText('#42')
    expect(screen.getByRole('button', { name: /visualizar/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /baixar pdf/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /histórico/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /editar/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /duplicar/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /desabilitar/i })).not.toBeInTheDocument()
  })

  it('Desabilitar confirma dizendo que da para reativar, e chama a API', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(<PropostasPage />)
    await screen.findByText('#42')
    fireEvent.click(screen.getByRole('button', { name: /desabilitar/i }))

    await waitFor(() => expect(desabilitar).toHaveBeenCalledWith(10))
    // O texto do confirm e o coracao da mudanca: nao pode mais prometer exclusao.
    const texto = confirmSpy.mock.calls[0][0] as string
    expect(texto).toMatch(/reativ/i)
    expect(texto).not.toMatch(/não pode ser desfeita/i)
    confirmSpy.mockRestore()
  })

  it('nao desabilita se o usuario cancelar o confirm', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
    render(<PropostasPage />)
    await screen.findByText('#42')
    fireEvent.click(screen.getByRole('button', { name: /desabilitar/i }))

    expect(desabilitar).not.toHaveBeenCalled()
    confirmSpy.mockRestore()
  })

  it('a lista pede as desabilitadas ao marcar o filtro', async () => {
    render(<PropostasPage />)
    await screen.findByText('#42')
    fireEvent.click(screen.getByLabelText(/mostrar desabilitadas/i))

    await waitFor(() =>
      expect(listar).toHaveBeenLastCalledWith(expect.objectContaining({ incluir_desabilitadas: true })))
  })

  it('proposta desabilitada aparece marcada, sem editar/duplicar, com Reativar para o Admin', async () => {
    listar.mockResolvedValue({
      items: [{ ...PROPOSTA, is_deleted: true, deleted_at: '2026-08-05T10:00:00Z' }],
      total: 1, page: 1, page_size: 25, total_pages: 1,
    })
    render(<PropostasPage />)
    await screen.findByText('#42')

    expect(screen.getByText('Desabilitada')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /editar/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /duplicar/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /desabilitar/i })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /reativar/i }))
    await waitFor(() => expect(reativar).toHaveBeenCalledWith(10))
  })

  it('quem nao e Admin nao ve o Reativar', async () => {
    useAuth.mockReturnValue({ user: USUARIO_FINANCEIRO })
    listar.mockResolvedValue({
      items: [{ ...PROPOSTA, is_deleted: true, deleted_at: '2026-08-05T10:00:00Z' }],
      total: 1, page: 1, page_size: 25, total_pages: 1,
    })
    render(<PropostasPage />)
    await screen.findByText('#42')

    expect(screen.getByText('Desabilitada')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /reativar/i })).not.toBeInTheDocument()
  })

  it('Visualizar abre a proposta numa modal embutida, sem aba nova', async () => {
    baixarPdf.mockResolvedValue(new Blob(['conteudo']))
    const openSpy = vi.spyOn(window, 'open')

    render(<PropostasPage />)
    await screen.findByText('#42')
    fireEvent.click(screen.getByRole('button', { name: /visualizar/i }))

    expect(await screen.findByText('Proposta #42')).toBeInTheDocument()
    await waitFor(() => expect(baixarPdf).toHaveBeenCalledWith(10))

    const frame = await screen.findByTitle('Proposta 42')
    expect(frame).toHaveAttribute('src', 'blob:mock')
    expect(openSpy).not.toHaveBeenCalled()

    openSpy.mockRestore()
  })

  it('mostra o selo Faturada quando a proposta está faturada', async () => {
    listar.mockResolvedValue({ items: [{ ...PROPOSTA, faturada: true }], total: 1, page: 1, page_size: 25, total_pages: 1 })
    render(<PropostasPage />)
    await screen.findByText('#42')
    expect(screen.getByText('Faturada')).toBeInTheDocument()
  })

  it('usuário Financeiro vê "Marcar como Faturada" numa proposta não-faturada e ao clicar chama propostasApi.faturar', async () => {
    useAuth.mockReturnValue({ user: USUARIO_FINANCEIRO })
    faturar.mockResolvedValue({ ...PROPOSTA, faturada: true })
    render(<PropostasPage />)
    await screen.findByText('#42')

    const botao = screen.getByRole('button', { name: /marcar como faturada/i })
    expect(botao).toBeInTheDocument()
    fireEvent.click(botao)
    await waitFor(() => expect(faturar).toHaveBeenCalledWith(10))
  })

  it('"Desfazer faturamento" aparece para o Admin numa proposta faturada', async () => {
    listar.mockResolvedValue({ items: [{ ...PROPOSTA, faturada: true }], total: 1, page: 1, page_size: 25, total_pages: 1 })
    useAuth.mockReturnValue({ user: USUARIO_ADMIN })
    render(<PropostasPage />)
    await screen.findByText('#42')
    expect(screen.getByRole('button', { name: /desfazer faturamento/i })).toBeInTheDocument()
  })

  it('"Desfazer faturamento" aparece para o Financeiro numa proposta faturada', async () => {
    // Era exclusivo do Admin ate 04/09/2026: quem marca o faturamento e' quem
    // descobre o engano, entao desfaz tambem.
    listar.mockResolvedValue({ items: [{ ...PROPOSTA, faturada: true }], total: 1, page: 1, page_size: 25, total_pages: 1 })
    useAuth.mockReturnValue({ user: USUARIO_FINANCEIRO })
    render(<PropostasPage />)
    await screen.findByText('#42')
    expect(screen.getByRole('button', { name: /desfazer faturamento/i })).toBeInTheDocument()
  })

  it('proposta sem dados editados nao mostra o selo', async () => {
    render(<PropostasPage />)
    await screen.findByText('#42')
    expect(screen.queryByText('Dados editados')).not.toBeInTheDocument()
  })

  it('selo "Dados editados" abre o comparativo cadastro x proposta', async () => {
    listar.mockResolvedValue({
      items: [{ ...PROPOSTA, cliente_nome: 'Filial Recife', cliente_override: { nome: 'Filial Recife', contato: 'Joao' } }],
      total: 1, page: 1, page_size: 25, total_pages: 1,
    })
    render(<PropostasPage />)
    await screen.findByText('#42')

    fireEvent.click(screen.getByRole('button', { name: /dados editados/i }))

    expect(await screen.findByText('Dados editados — Proposta #42')).toBeInTheDocument()
    await waitFor(() => expect(clientesObter).toHaveBeenCalledWith(5))
    // lado do cadastro
    await screen.findByText('Cliente Teste')
    await screen.findByText('Ana')
    // lado da proposta (o nome aparece tambem na linha da tabela)
    expect(screen.getAllByText('Filial Recife').length).toBeGreaterThan(0)
    expect(screen.getByText('Joao')).toBeInTheDocument()
    // campo nao editado nao entra
    expect(screen.queryByText('E-mail')).not.toBeInTheDocument()
  })

  it('override que repete o cadastro aparece marcado como igual', async () => {
    listar.mockResolvedValue({
      items: [{ ...PROPOSTA, cliente_override: { nome: 'Cliente Teste' } }],
      total: 1, page: 1, page_size: 25, total_pages: 1,
    })
    render(<PropostasPage />)
    await screen.findByText('#42')

    fireEvent.click(screen.getByRole('button', { name: /dados editados/i }))
    expect(await screen.findByText('(igual ao cadastro)')).toBeInTheDocument()
  })
})
