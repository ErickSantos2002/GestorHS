// Override de cliente/contato por proposta: os dados que valem SO naquela
// proposta, sem tocar no cadastro. Este modulo e a fonte unica dos campos
// suportados, dos rotulos e da comparacao cadastro x proposta — usado pelo
// editor (PropostaModal), pela listagem e pela tela de detalhe.

import { formatarDocumento, mascararCEP, soDigitos } from '../../lib/documento'
import type { Cliente } from '../clientes/api'

// As chaves DEVEM bater com o backend (app/core/proposta_pdf.py, montagem do contexto).
export const CAMPOS_OVERRIDE = ['nome', 'documento', 'endereco', 'municipio', 'estado', 'cep', 'email', 'telefone', 'contato'] as const
export type CampoOverride = (typeof CAMPOS_OVERRIDE)[number]

export const ROTULOS_OVERRIDE: Record<CampoOverride, string> = {
  nome: 'Razão social / Nome',
  documento: 'CNPJ / Documento',
  endereco: 'Endereço',
  municipio: 'Município',
  estado: 'Estado (UF)',
  cep: 'CEP',
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
    case 'cep': return soDigitos(cliente.cep)
    case 'email': return cliente.email ?? ''
    case 'telefone': return cliente.celular || cliente.whatsapp || cliente.telefones || ''
    case 'contato': return cliente.contato ?? ''
  }
}

/**
 * O que o rascunho do painel viraria no override da proposta.
 *
 * Guarda SO o que diverge do cadastro: o painel abre pre-preenchido, entao
 * gravar tudo marcaria a proposta como "Dados editados" sem nada divergir de
 * fato. Campo em branco tambem fica de fora — em branco significa "usa o
 * cadastro", e e' assim que o PDF resolve cada campo.
 *
 * Vive aqui, e nao no modal, porque duas telas precisam da MESMA resposta:
 * a que aplica o rascunho e a que decide se ha edicao pendente ao fechar.
 */
export function overrideDoRascunho(
  rascunho: Partial<Record<CampoOverride, string>>,
  cliente?: Cliente | null,
): Record<string, string> | null {
  const limpo: Record<string, string> = {}
  CAMPOS_OVERRIDE.forEach((campo) => {
    const v = rascunho[campo]
    if (v == null || v.trim() === '') return
    if (mesmoValorDoCadastro(campo, v, cliente)) return
    limpo[campo] = v.trim()
  })
  return Object.keys(limpo).length ? limpo : null
}

/** Dois overrides com o mesmo conteudo, independente da ordem das chaves.
 *  A ordem importa porque um vem do servidor e o outro e' montado aqui. */
export function mesmoOverride(
  a?: Record<string, unknown> | null,
  b?: Record<string, unknown> | null,
): boolean {
  const ea = Object.entries(a ?? {}).sort(([x], [y]) => x.localeCompare(y))
  const eb = Object.entries(b ?? {}).sort(([x], [y]) => x.localeCompare(y))
  return ea.length === eb.length
    && ea.every(([k, v], i) => k === eb[i][0] && String(v ?? '') === String(eb[i][1] ?? ''))
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

// Campos guardados como digitos puros — mascara e' so apresentacao.
const CAMPOS_DIGITOS = new Set<CampoOverride>(['documento', 'cep'])

function normalizarCampo(campo: CampoOverride, v: string): string {
  return CAMPOS_DIGITOS.has(campo) ? soDigitos(v) : v.trim()
}

function exibirCampo(campo: CampoOverride, v: string): string {
  if (campo === 'documento') return formatarDocumento(v)
  if (campo === 'cep') return mascararCEP(v)
  return v
}

/** true quando o valor digitado equivale ao que ja esta no cadastro. */
export function mesmoValorDoCadastro(campo: CampoOverride, valor: string, cliente?: Cliente | null): boolean {
  return normalizarCampo(campo, valor) === normalizarCampo(campo, valorDoCadastro(campo, cliente))
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

  return CAMPOS_OVERRIDE.flatMap((campo) => {
    const bruto = String(override[campo] ?? '').trim()
    if (!bruto) return []
    const cadastro = valorDoCadastro(campo, cliente)
    return [{
      campo,
      rotulo: ROTULOS_OVERRIDE[campo],
      cadastro: exibirCampo(campo, cadastro),
      proposta: exibirCampo(campo, bruto),
      mudou: normalizarCampo(campo, bruto) !== normalizarCampo(campo, cadastro),
    }]
  })
}
