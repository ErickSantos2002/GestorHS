// Override de cliente/contato por proposta: os dados que valem SO naquela
// proposta, sem tocar no cadastro. Este modulo e a fonte unica dos campos
// suportados, dos rotulos e da comparacao cadastro x proposta — usado pelo
// editor (PropostaModal), pela listagem e pela tela de detalhe.

import { formatarDocumento, soDigitos } from '../../lib/documento'
import type { Cliente } from '../clientes/api'

// As chaves DEVEM bater com o backend (app/core/proposta_pdf.py, montagem do contexto).
export const CAMPOS_OVERRIDE = ['nome', 'documento', 'endereco', 'municipio', 'estado', 'email', 'telefone', 'contato'] as const
export type CampoOverride = (typeof CAMPOS_OVERRIDE)[number]

export const ROTULOS_OVERRIDE: Record<CampoOverride, string> = {
  nome: 'Razão social / Nome',
  documento: 'CNPJ / Documento',
  endereco: 'Endereço',
  municipio: 'Município',
  estado: 'Estado (UF)',
  email: 'E-mail',
  telefone: 'Telefone',
  contato: 'Contato',
}

export function temOverride(o?: Record<string, unknown> | null): boolean {
  return !!o && Object.values(o).some((v) => v != null && String(v).trim() !== '')
}

/** Valor equivalente no cadastro do cliente, para comparar com o override. */
export function valorDoCadastro(campo: CampoOverride, cliente?: Cliente | null): string {
  if (!cliente) return ''
  switch (campo) {
    case 'nome': return cliente.nome ?? ''
    case 'documento': return soDigitos(cliente.cgc || cliente.cpf || '')
    case 'endereco': return cliente.endereco ?? ''
    case 'municipio': return cliente.municipio ?? ''
    case 'estado': return cliente.estado ?? ''
    case 'email': return cliente.email ?? ''
    case 'telefone': return cliente.celular || cliente.whatsapp || cliente.telefones || ''
    case 'contato': return cliente.contato ?? ''
  }
}

export interface CampoAlterado {
  campo: CampoOverride
  rotulo: string
  /** Ja formatado para exibicao (documento com mascara). */
  cadastro: string
  proposta: string
  /** false quando o override repete o que ja esta no cadastro (edicao inofensiva). */
  mudou: boolean
}

/**
 * Campos preenchidos no override, com o valor do cadastro ao lado.
 * Campos em branco no override nao entram — eles caem no cadastro.
 * `cliente` ausente (nao carregado / cliente removido) deixa o lado do
 * cadastro vazio, mas os valores da proposta continuam visiveis.
 */
export function camposAlterados(
  override?: Record<string, unknown> | null,
  cliente?: Cliente | null,
): CampoAlterado[] {
  if (!override) return []
  const exibir = (campo: CampoOverride, v: string) => (campo === 'documento' ? formatarDocumento(v) : v)

  return CAMPOS_OVERRIDE.flatMap((campo) => {
    const bruto = String(override[campo] ?? '').trim()
    if (!bruto) return []
    const cadastro = valorDoCadastro(campo, cliente)
    const normalizar = (v: string) => (campo === 'documento' ? soDigitos(v) : v.trim())
    return [{
      campo,
      rotulo: ROTULOS_OVERRIDE[campo],
      cadastro: exibir(campo, cadastro),
      proposta: exibir(campo, bruto),
      mudou: normalizar(bruto) !== normalizar(cadastro),
    }]
  })
}
