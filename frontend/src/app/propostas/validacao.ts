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
 * Telefone e contato ficam de fora a pedido do comercial: nem todo cliente tem
 * um, e travar a proposta por isso atrapalharia mais do que ajuda. O e-mail,
 * que nasce vazio de proposito (ver `NAO_HERDADOS` em clienteOverride), so e'
 * conferido a cada proposta porque esta nesta lista.
 */
export const CAMPOS_OBRIGATORIOS: readonly CampoOverride[] = [
  'nome', 'documento', 'endereco', 'municipio', 'estado', 'cep', 'email',
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
