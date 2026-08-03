import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { CertificadosGeraisTab } from './CertificadosGeraisTab'
import { ApiError } from '../../lib/api'

vi.mock('./api', () => ({
  certificadosApi: {
    listarGerais: vi.fn(),
    enviarGeral: vi.fn(),
    excluirGeral: vi.fn(),
  },
}))

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ user: { funcao: 'Administrador' } }),
}))

import { certificadosApi } from './api'

const ITENS = [
  { id: 1, nome: 'Certificado do Gás', data_upload: '2026-01-05', usuario_nome: 'Erick', link: 'https://x/1' },
]

describe('CertificadosGeraisTab', () => {
  beforeEach(() => {
    vi.mocked(certificadosApi.listarGerais).mockResolvedValue(ITENS)
  })

  it('mostra a mensagem do backend quando a exclusao falha (409 em uso na configuracao)', async () => {
    window.confirm = vi.fn(() => true)
    vi.mocked(certificadosApi.excluirGeral).mockRejectedValue(
      new ApiError(409, 'Este documento está selecionado em Configurações. Desmarque-o lá antes de excluir.'),
    )
    render(<CertificadosGeraisTab />)
    await waitFor(() => expect(screen.getByText('Certificado do Gás')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /excluir/i }))

    await waitFor(() =>
      expect(
        screen.getByText('Este documento está selecionado em Configurações. Desmarque-o lá antes de excluir.'),
      ).toBeInTheDocument(),
    )
  })
})
