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

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ user: { funcao: 'Administrador' } }),
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
})
