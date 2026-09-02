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
 * Campos do painel do cliente, na ordem em que aparecem no formulario.
 *
 * `contato` fica de fora de proposito: "aos cuidados de" e' campo da PROPOSTA
 * (coluna `propostas.contato`), nao um override do cadastro do cliente. Guardar
 * o contato no override quebrava quando o valor digitado coincidia com o do
 * cadastro — `overrideDoRascunho` descartava, a coluna ficava vazia e o PDF
 * saia sem o "aos cuidados de".
 */
export const CAMPOS_RASCUNHO = [
  'nome', 'documento', 'endereco', 'municipio', 'estado', 'cep', 'telefone', 'email',
] as const

/**
 * Campos que NUNCA sao herdados do cadastro: nascem vazios em toda proposta e
 * so aparecem preenchidos se aquela proposta ja gravou um valor proprio.
 *
 * O e-mail entrou aqui a pedido do comercial: vindo pronto do cadastro, ninguem
 * conferia, e proposta saia com e-mail antigo do cliente. Vazio + obrigatorio
 * (ver `validacao.ts`) forca a conferencia a cada proposta.
 */
const NAO_HERDADOS = new Set<CampoOverride>(['email'])

/**
 * Estado inicial do painel: cadastro do cliente por baixo, override da proposta
 * por cima, campo a campo.
 *
 * O painel vive aberto, entao este rascunho e' a fonte unica dos dados do
 * cliente na proposta — o `cliente_override` e' derivado dele
 * (`overrideDoRascunho`), nunca o contrario.
 */
export function montarRascunho(
  cliente?: Cliente | null,
  override?: Record<string, unknown> | null,
): Partial<Record<CampoOverride, string>> {
  const rascunho: Partial<Record<CampoOverride, string>> = {}
  CAMPOS_RASCUNHO.forEach((campo) => {
    const doCadastro = NAO_HERDADOS.has(campo) ? '' : valorDoCadastro(campo, cliente)
    const doOverride = String(override?.[campo] ?? '').trim()
    rascunho[campo] = doOverride ? normalizarCampo(campo, doOverride) : doCadastro
  })
  return rascunho
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
