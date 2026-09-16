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
 * O documento so e' exigido de empresa NOVA: no cadastro existente ele e'
 * somente leitura, e Cliente antigo sem CNPJ/CPF nao pode virar beco sem saida.
 */
export function obrigatoriosDaProposta(exigirDocumento: boolean): readonly CampoDados[] {
  return exigirDocumento ? OBRIGATORIOS_PROPOSTA : OBRIGATORIOS_PROPOSTA.filter((c) => c !== 'documento')
}

/**
 * Rotulos dos obrigatorios vazios, na ordem do formulario. E-mail, telefone e
 * "aos cuidados de" nascem vazios de proposito e so sao conferidos porque estao
 * aqui — herdados do cadastro, ninguem olhava (pedido do comercial).
 */
export function camposObrigatoriosFaltando(dados: DadosEmpresa, contato: string, exigirDocumento: boolean): string[] {
  const faltando = camposFaltando(dados, obrigatoriosDaProposta(exigirDocumento)).map((c) => ROTULOS_DADOS[c])
  if (contato.trim() === '') faltando.push(ROTULO_CONTATO)
  return faltando
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
