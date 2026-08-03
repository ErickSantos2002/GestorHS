import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { ConfiguracoesTab } from './ConfiguracoesTab'

vi.mock('./api', () => ({
  certificadosApi: {
    config: vi.fn(),
    salvarConfig: vi.fn(),
    padroes: vi.fn(),
    criarPadrao: vi.fn(),
    atualizarPadrao: vi.fn(),
    excluirPadrao: vi.fn(),
    listarGerais: vi.fn(),
  },
}))

// Estado mutavel para variar o usuario logado por teste — vi.mock e hoisted, entao
// o valor lido pelo mock precisa vir de um objeto criado via vi.hoisted().
const authState = vi.hoisted(() => ({ user: { funcao: 'Administrador' } as { funcao: string } | null }))

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ user: authState.user }),
}))

import { certificadosApi } from './api'

const CONFIG = {
  id: 1, valor_referencia: '0.1000', limite_minimo: '0.1500', limite_maximo: '0.1900',
  resolucao_instrumento: '0.1000', incerteza_padrao_temp: '0.0520',
  resolucao_pressao: null, incerteza_padrao_pressao: null, fator_k: '2.00',
  tecnico_nome: 'Walbert Santos', tecnico_cargo: 'Técnico em Metrologia',
  equipamentos_auxiliares: 'TESTO 622', margem_temperatura: '20 ºC ~ 24 ºC',
  doc_gas_id: null as number | null, doc_termohigrometro_id: null as number | null, doc_barometro_id: null as number | null,
}

const GERAIS = [
  { id: 1, nome: 'Certificado do Gás', data_upload: null, usuario_nome: null, link: 'https://x/1' },
  { id: 3, nome: 'LV09700-06672-26', data_upload: null, usuario_nome: null, link: 'https://x/3' },
]

const CILINDRO = {
  id: 7, numero_cilindro: 'CC747704', numero_certificado: '202231419',
  concentracao: '100.1000', incerteza_concentracao: '2.0000',
  unidade: 'µmol/mol', vigencia_inicio: '2025-01-01', vigencia_fim: null as string | null, ativo: true,
}

describe('ConfiguracoesTab', () => {
  beforeEach(() => {
    authState.user = { funcao: 'Administrador' }
    vi.mocked(certificadosApi.config).mockResolvedValue(CONFIG)
    vi.mocked(certificadosApi.padroes).mockResolvedValue([{ ...CILINDRO }])
    vi.mocked(certificadosApi.atualizarPadrao).mockReset()
    vi.mocked(certificadosApi.salvarConfig).mockReset()
    vi.mocked(certificadosApi.listarGerais).mockResolvedValue(GERAIS)
  })

  it('carrega e mostra os parametros do calculo', async () => {
    render(<ConfiguracoesTab />)
    await waitFor(() => expect(screen.getByLabelText(/valor de refer/i)).toHaveValue('0.1000'))
    expect(screen.getByLabelText(/t.cnico respons/i)).toHaveValue('Walbert Santos')
  })

  it('lista os cilindros cadastrados', async () => {
    render(<ConfiguracoesTab />)
    await waitFor(() => expect(screen.getByText('CC747704')).toBeInTheDocument())
    expect(screen.getByText('202231419')).toBeInTheDocument()
  })

  it('esconde os controles de edicao e desabilita os campos para nao-admin', async () => {
    authState.user = { funcao: 'Laboratório' }
    render(<ConfiguracoesTab />)
    await waitFor(() => expect(screen.getByText('CC747704')).toBeInTheDocument())

    expect(screen.getByLabelText(/valor de refer/i)).toBeDisabled()
    // Os selects de documento tambem: sao o que decide qual PDF o cliente baixa pelo QR
    expect(screen.getByLabelText(/certificado do g.s/i)).toBeDisabled()
    expect(screen.getByLabelText(/termohigr/i)).toBeDisabled()
    expect(screen.getByLabelText(/bar.metro/i)).toBeDisabled()
    expect(screen.queryByRole('button', { name: /salvar/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /adicionar/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /excluir/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /encerrar vig/i })).not.toBeInTheDocument()
  })

  it('marca um so cilindro como Em uso quando dois estao em aberto', async () => {
    // Fluxo esperado da troca de gás: cadastra-se o cilindro novo e o antigo fica
    // sem vigência fim. O backend (padrao_vigente) escolhe o de início mais recente —
    // a tabela tem de dizer a mesma coisa, e uma só vez.
    vi.mocked(certificadosApi.padroes).mockResolvedValue([
      { ...CILINDRO, id: 8, numero_cilindro: 'NOVO', vigencia_inicio: '2026-01-01' },
      { ...CILINDRO, id: 7, numero_cilindro: 'ANTIGO', vigencia_inicio: '2025-01-01' },
    ])
    render(<ConfiguracoesTab />)
    await waitFor(() => expect(screen.getByText('NOVO')).toBeInTheDocument())

    expect(screen.getAllByText('Em uso')).toHaveLength(1)
    const linhaNovo = screen.getByText('NOVO').closest('tr')!
    expect(linhaNovo).toHaveTextContent('Em uso')
  })

  it('encerra a vigencia do cilindro pela API', async () => {
    vi.mocked(certificadosApi.atualizarPadrao).mockResolvedValue({ ...CILINDRO, vigencia_fim: '2026-08-03' })
    render(<ConfiguracoesTab />)
    await waitFor(() => expect(screen.getByText('CC747704')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /encerrar vig/i }))
    await waitFor(() => expect(certificadosApi.atualizarPadrao).toHaveBeenCalledTimes(1))
    expect(vi.mocked(certificadosApi.atualizarPadrao).mock.calls[0][0]).toBe(7)
    expect(vi.mocked(certificadosApi.atualizarPadrao).mock.calls[0][1]).toHaveProperty('vigencia_fim')
    await waitFor(() => expect(screen.getByText('Vigência encerrada.')).toBeInTheDocument())
  })

  it('nao oferece encerrar vigencia em cilindro que ja tem fim', async () => {
    vi.mocked(certificadosApi.padroes).mockResolvedValue([{ ...CILINDRO, vigencia_fim: '2025-12-31' }])
    render(<ConfiguracoesTab />)
    await waitFor(() => expect(screen.getByText('CC747704')).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: /encerrar vig/i })).not.toBeInTheDocument()
  })

  it('edita o cilindro pela API e mostra o resultado na linha', async () => {
    vi.mocked(certificadosApi.atualizarPadrao).mockResolvedValue({
      ...CILINDRO, numero_cilindro: 'CC999999', numero_certificado: '202299999',
    })
    render(<ConfiguracoesTab />)
    await waitFor(() => expect(screen.getByText('CC747704')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /^editar$/i }))
    fireEvent.change(screen.getByLabelText('Editar cilindro'), { target: { value: 'CC999999' } })
    fireEvent.change(screen.getByLabelText('Editar certificado'), { target: { value: '202299999' } })
    fireEvent.click(screen.getByRole('button', { name: /^salvar cilindro$/i }))

    await waitFor(() => expect(certificadosApi.atualizarPadrao).toHaveBeenCalledTimes(1))
    const [id, dados] = vi.mocked(certificadosApi.atualizarPadrao).mock.calls[0]
    expect(id).toBe(7)
    expect(dados).toMatchObject({ numero_cilindro: 'CC999999', numero_certificado: '202299999' })
    // a linha passa a mostrar o valor novo, sem precisar recarregar a aba
    await waitFor(() => expect(screen.getByText('CC999999')).toBeInTheDocument())
  })

  it('cancelar a edicao nao chama a API nem altera a linha', async () => {
    render(<ConfiguracoesTab />)
    await waitFor(() => expect(screen.getByText('CC747704')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /^editar$/i }))
    fireEvent.change(screen.getByLabelText('Editar cilindro'), { target: { value: 'NAO DEVE GRAVAR' } })
    fireEvent.click(screen.getByRole('button', { name: /^cancelar$/i }))

    expect(certificadosApi.atualizarPadrao).not.toHaveBeenCalled()
    expect(screen.getByText('CC747704')).toBeInTheDocument()
  })

  it('campo vazio na edicao vira nulo, nao string vazia', async () => {
    vi.mocked(certificadosApi.atualizarPadrao).mockResolvedValue(CILINDRO)
    render(<ConfiguracoesTab />)
    await waitFor(() => expect(screen.getByText('CC747704')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /^editar$/i }))
    fireEvent.change(screen.getByLabelText('Editar certificado'), { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: /^salvar cilindro$/i }))

    await waitFor(() => expect(certificadosApi.atualizarPadrao).toHaveBeenCalledTimes(1))
    expect(vi.mocked(certificadosApi.atualizarPadrao).mock.calls[0][1].numero_certificado).toBeNull()
  })

  it('nao oferece editar para nao-admin', async () => {
    authState.user = { funcao: 'Laboratório' }
    render(<ConfiguracoesTab />)
    await waitFor(() => expect(screen.getByText('CC747704')).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: /^editar$/i })).not.toBeInTheDocument()
  })

  it('lista os documentos gerais nos tres selects', async () => {
    render(<ConfiguracoesTab />)
    await waitFor(() => expect(screen.getByLabelText(/certificado do g.s/i)).toBeInTheDocument())
    expect(screen.getByLabelText(/termohigr/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/bar.metro/i)).toBeInTheDocument()
    // cada select oferece os documentos cadastrados
    expect(screen.getAllByRole('option', { name: 'LV09700-06672-26' })).toHaveLength(3)
  })

  it('mostra a selecao ja salva de um documento, nao so o placeholder', async () => {
    // CONFIG no resto do arquivo tem os tres doc_*_id nulos: sem este teste, um bug
    // que impedisse o select de refletir um id ja gravado passaria por "nao salvou".
    vi.mocked(certificadosApi.config).mockResolvedValue({ ...CONFIG, doc_gas_id: 1 })
    render(<ConfiguracoesTab />)
    await waitFor(() => expect(screen.getByLabelText(/certificado do g.s/i)).toBeInTheDocument())
    expect(screen.getByLabelText(/certificado do g.s/i)).toHaveValue('1')
  })

  it('salva os ids dos documentos escolhidos', async () => {
    vi.mocked(certificadosApi.salvarConfig).mockResolvedValue({ ...CONFIG, doc_gas_id: 1 })
    render(<ConfiguracoesTab />)
    await waitFor(() => expect(screen.getByLabelText(/certificado do g.s/i)).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText(/certificado do g.s/i), { target: { value: '1' } })
    fireEvent.click(screen.getByRole('button', { name: /^salvar$/i }))

    await waitFor(() => expect(certificadosApi.salvarConfig).toHaveBeenCalledTimes(1))
    expect(vi.mocked(certificadosApi.salvarConfig).mock.calls[0][0]).toMatchObject({ doc_gas_id: 1 })
  })

  it('nenhum documento selecionado envia nulo, nao string vazia', async () => {
    vi.mocked(certificadosApi.salvarConfig).mockResolvedValue(CONFIG)
    render(<ConfiguracoesTab />)
    await waitFor(() => expect(screen.getByLabelText(/certificado do g.s/i)).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText(/certificado do g.s/i), { target: { value: '' } })
    fireEvent.click(screen.getByRole('button', { name: /^salvar$/i }))

    await waitFor(() => expect(certificadosApi.salvarConfig).toHaveBeenCalledTimes(1))
    expect(vi.mocked(certificadosApi.salvarConfig).mock.calls[0][0].doc_gas_id).toBeNull()
  })
})
