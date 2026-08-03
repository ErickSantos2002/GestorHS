import { describe, expect, it } from 'vitest'
import { padraoVigente } from './padraoVigente'
import type { CertificadoPadrao } from './api'

function cilindro(over: Partial<CertificadoPadrao> = {}): CertificadoPadrao {
  return {
    id: 1, numero_cilindro: 'CC747704', numero_certificado: '202231419',
    concentracao: '100.1000', incerteza_concentracao: '2.0000', unidade: 'µmol/mol',
    vigencia_inicio: '2025-01-01', vigencia_fim: null, ativo: true,
    ...over,
  }
}

// Estes casos são os mesmos de test_certificado_config.py::test_padrao_vigente_* —
// as duas implementações da regra precisam responder igual.
describe('padraoVigente', () => {
  it('resolve pela data', () => {
    const antigo = cilindro({ id: 1, vigencia_inicio: '2024-01-01', vigencia_fim: '2024-12-31' })
    const atual = cilindro({ id: 2, vigencia_inicio: '2025-01-01' })
    expect(padraoVigente([antigo, atual], '2024-06-01')?.id).toBe(1)
    expect(padraoVigente([antigo, atual], '2026-06-01')?.id).toBe(2)
  })

  it('sem correspondencia devolve null — nao cai no cilindro atual', () => {
    expect(padraoVigente([cilindro()], '2020-01-01')).toBeNull()
  })

  it('ignora cilindro inativo', () => {
    expect(padraoVigente([cilindro({ ativo: false })], '2026-01-01')).toBeNull()
  })

  it('ignora cilindro sem data de inicio', () => {
    // o filtro do backend e `vigencia_inicio <= data`, que em SQL nunca casa com NULL
    expect(padraoVigente([cilindro({ vigencia_inicio: null })], '2026-01-01')).toBeNull()
  })

  it('entre dois em aberto, vence o de inicio mais recente', () => {
    const antigo = cilindro({ id: 1, vigencia_inicio: '2025-01-01' })
    const novo = cilindro({ id: 2, vigencia_inicio: '2026-01-01' })
    expect(padraoVigente([antigo, novo], '2026-08-03')?.id).toBe(2)
  })

  it('empate de inicio desempata pelo id maior, como o ORDER BY do backend', () => {
    const a = cilindro({ id: 1, vigencia_inicio: '2025-01-01' })
    const b = cilindro({ id: 2, vigencia_inicio: '2025-01-01' })
    expect(padraoVigente([a, b], '2026-01-01')?.id).toBe(2)
    expect(padraoVigente([b, a], '2026-01-01')?.id).toBe(2)
  })

  it('lista vazia devolve null', () => {
    expect(padraoVigente([], '2026-01-01')).toBeNull()
  })
})
