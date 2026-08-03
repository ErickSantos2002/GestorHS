import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { ConfiguracoesTab } from './ConfiguracoesTab'

vi.mock('./api', () => ({
  certificadosApi: {
    config: vi.fn(),
    salvarConfig: vi.fn(),
    padroes: vi.fn(),
    criarPadrao: vi.fn(),
    excluirPadrao: vi.fn(),
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
}

describe('ConfiguracoesTab', () => {
  beforeEach(() => {
    authState.user = { funcao: 'Administrador' }
    vi.mocked(certificadosApi.config).mockResolvedValue(CONFIG)
    vi.mocked(certificadosApi.padroes).mockResolvedValue([{
      id: 7, numero_cilindro: 'CC747704', numero_certificado: '202231419',
      concentracao: '100.1000', incerteza_concentracao: '2.0000',
      unidade: 'µmol/mol', vigencia_inicio: '2025-01-01', vigencia_fim: null, ativo: true,
    }])
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
    expect(screen.queryByRole('button', { name: /salvar/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /adicionar/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /excluir/i })).not.toBeInTheDocument()
  })
})
