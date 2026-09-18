// Regras minimas para uma proposta sair do modal. Existem porque o backend
// aceita quase tudo opcional e o submit implicito do browser (Enter) chegou a
// criar propostas em branco — ver PropostaModal.

import { camposFaltando, OBRIGATORIOS_PROPOSTA, ROTULOS_DADOS, type CampoDados, type DadosEmpresa } from '../empresas/dadosEmpresa'
import type { Selecao } from './destinatario'

/**
 * O editor rico (Quill) nunca devolve string vazia depois de tocado: sobra
 * `<p><br></p>`, `&nbsp;` e afins. Aqui interessa se ha TEXTO, nao markup.
 */
export function htmlTemTexto(html?: string | null): boolean {
  if (!html) return false
  return html.replace(/<[^>]*>/g, ' ').replace(/&nbsp;/gi, ' ').trim() !== ''
}

export const ROTULO_CONTATO = 'Contato (aos cuidados de)'

/**
 * Campos que a proposta NAO exige, embora a pagina Empresas exija:
 *
 * - `documento`: so de empresa NOVA. No cadastro existente ele e' somente
 *   leitura, e Cliente antigo sem CNPJ/CPF nao pode virar beco sem saida.
 * - `telefone` e `email`: opcionais desde 18/09/2026. Em branco o backend NAO
 *   altera o cadastro do cliente/empresa — nem apaga, nem grava. Antes eram
 *   exigidos a cada proposta (pedido do comercial, porque herdados do cadastro
 *   ninguem olhava); o pedido foi revertido.
 */
const NAO_EXIGIDOS_NA_PROPOSTA: readonly CampoDados[] = ['telefone', 'email']

export function obrigatoriosDaProposta(exigirDocumento: boolean): readonly CampoDados[] {
  const fora = new Set<CampoDados>(NAO_EXIGIDOS_NA_PROPOSTA)
  if (!exigirDocumento) fora.add('documento')
  return OBRIGATORIOS_PROPOSTA.filter((c) => !fora.has(c))
}

/**
 * Rotulos dos obrigatorios vazios, na ordem do formulario.
 *
 * `contato` ("aos cuidados de") tambem deixou de ser exigido em 18/09/2026 — ele
 * vive so em `propostas.contato` e nunca chega ao cadastro. O parametro fica na
 * assinatura porque `validarProposta` o repassa; ignora-lo aqui e' deliberado.
 */
export function camposObrigatoriosFaltando(dados: DadosEmpresa, _contato: string, exigirDocumento: boolean): string[] {
  return camposFaltando(dados, obrigatoriosDaProposta(exigirDocumento)).map((c) => ROTULOS_DADOS[c])
}

export interface PropostaValidavel {
  selecao: Selecao | null
  dados: DadosEmpresa
  contato: string
  outrosItens?: string | null
  /** Dados do destinatario ainda carregando — nao da para julgar os campos. */
  carregando?: boolean
}

/** Devolve a mensagem do primeiro problema encontrado, ou null se estiver ok. */
export function validarProposta(p: PropostaValidavel): string | null {
  if (p.selecao == null) return 'Escolha o destinatário antes de salvar a proposta.'
  if (p.carregando) return 'Aguarde o carregamento dos dados do destinatário.'
  const faltando = camposObrigatoriosFaltando(p.dados, p.contato, p.selecao.tipo === 'nova_empresa')
  if (faltando.length) return `Preencha os campos obrigatórios: ${faltando.join(', ')}.`
  if (!htmlTemTexto(p.outrosItens)) return 'Preencha "Outros Itens ou Serviços" — use o botao Aplicar modelo.'
  return null
}
