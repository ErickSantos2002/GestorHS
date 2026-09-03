// Regras minimas para uma proposta sair do modal. Existem porque o backend
// aceita quase tudo opcional e o submit implicito do browser (Enter) chegou a
// criar propostas em branco — ver PropostaModal.

import { soDigitos } from '../../lib/documento'
import { ROTULOS_OVERRIDE, type CampoOverride } from './clienteOverride'

/**
 * O editor rico (Quill) nunca devolve string vazia depois de tocado: sobra
 * `<p><br></p>`, `&nbsp;` e afins. Aqui interessa se ha TEXTO, nao markup.
 */
export function htmlTemTexto(html?: string | null): boolean {
  if (!html) return false
  return html
    .replace(/<[^>]*>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .trim() !== ''
}

/**
 * Campos do cliente que a proposta nao pode levar em branco, na ordem em que
 * aparecem no formulario.
 *
 * Telefone, e-mail e contato entraram a pedido do comercial: os tres nascem
 * vazios de proposito (ver `NAO_HERDADOS` em clienteOverride) e so sao
 * conferidos a cada proposta porque estao nesta lista — herdados do cadastro,
 * ninguem olhava e a proposta saia com o contato velho do cliente.
 *
 * `contato` nao e' campo do rascunho do override (mora em `propostas.contato`,
 * ver CAMPOS_RASCUNHO): quem valida injeta o valor do form no rascunho so para
 * esta checagem — ver PropostaModal.
 */
export const CAMPOS_OBRIGATORIOS: readonly CampoOverride[] = [
  'nome', 'documento', 'endereco', 'municipio', 'estado', 'cep', 'telefone', 'email', 'contato',
]

// Campos guardados como digitos: pontuacao sozinha nao e' preenchimento.
const SO_DIGITOS = new Set<CampoOverride>(['documento', 'cep'])

/** Quais obrigatorios estao vazios no rascunho do painel do cliente. */
export function camposObrigatoriosFaltando(
  rascunho: Partial<Record<CampoOverride, string>>,
): CampoOverride[] {
  return CAMPOS_OBRIGATORIOS.filter((campo) => {
    const v = rascunho[campo] ?? ''
    return SO_DIGITOS.has(campo) ? !soDigitos(v) : v.trim() === ''
  })
}

export interface PropostaValidavel {
  cliente: number | null
  /** Rascunho do painel do cliente — o que a proposta vai levar, campo a campo. */
  rascunho: Partial<Record<CampoOverride, string>>
  /** HTML do campo "Outros Itens ou Serviços". */
  outrosItens?: string | null
  /** Dados do cliente ainda em carregamento — nao da para julgar os campos. */
  carregandoCliente?: boolean
}

/** Devolve a mensagem do primeiro problema encontrado, ou null se estiver ok. */
export function validarProposta(p: PropostaValidavel): string | null {
  if (p.cliente == null) return 'Selecione o cliente antes de salvar a proposta.'
  if (p.carregandoCliente) return 'Aguarde o carregamento dos dados do cliente.'
  const faltando = camposObrigatoriosFaltando(p.rascunho)
  if (faltando.length) {
    const rotulos = faltando.map((c) => ROTULOS_OVERRIDE[c]).join(', ')
    return `Preencha os campos obrigatórios do cliente: ${rotulos}.`
  }
  if (!htmlTemTexto(p.outrosItens)) {
    return 'Preencha "Outros Itens ou Serviços" — use o botao Aplicar modelo.'
  }
  return null
}
