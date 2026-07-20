import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { PortalCertificadosPage } from './PortalCertificadosPage'
import { portalApi } from './api'

beforeEach(() => { vi.restoreAllMocks() })

function item(over: Record<string, unknown> = {}) {
  return {
    equipamento_cliente: 1, equipamento_descricao: 'Mark X', serie: 'S1',
    calib_cert: 'V-001', ult_calibragem: '2026-07-20', prox_calibragem: '2027-07-20',
    pdf: null, os: null, venda: false, ...over,
  }
}

describe('PortalCertificadosPage', () => {
  it('oferece download quando o aparelho so tem certificado de venda', async () => {
    vi.spyOn(portalApi, 'certificados').mockResolvedValue({ items: [item({ venda: true })], total: 1 } as never)
    render(<PortalCertificadosPage />)
    await waitFor(() => expect(screen.getByRole('button', { name: 'Baixar' })).toBeInTheDocument())
  })

  it('nao oferece download sem OS e sem certificado de venda', async () => {
    vi.spyOn(portalApi, 'certificados').mockResolvedValue({ items: [item()], total: 1 } as never)
    render(<PortalCertificadosPage />)
    await waitFor(() => expect(screen.getByText('Mark X')).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: 'Baixar' })).not.toBeInTheDocument()
  })
})
