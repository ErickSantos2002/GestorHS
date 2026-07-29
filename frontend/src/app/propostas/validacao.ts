// Regras minimas para uma proposta sair do modal. Existem porque o backend
// aceita quase tudo opcional e o submit implicito do browser (Enter) chegou a
// criar propostas em branco — ver PropostaModal.

import { soDigitos } from '../../lib/documento'

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

export interface PropostaValidavel {
  cliente: number | null
  /** Documento em vigor nesta proposta: override, se houver, senao o do cadastro. */
  documento?: string | null
  /** HTML do campo "Outros Itens ou Serviços". */
  outrosItens?: string | null
  /** Dados do cliente ainda em carregamento — nao da para julgar o documento. */
  carregandoCliente?: boolean
}

/** Devolve a mensagem do primeiro problema encontrado, ou null se estiver ok. */
export function validarProposta(p: PropostaValidavel): string | null {
  if (p.cliente == null) return 'Selecione o cliente antes de salvar a proposta.'
  if (p.carregandoCliente) return 'Aguarde o carregamento dos dados do cliente.'
  if (!soDigitos(p.documento ?? '')) {
    return 'O cliente selecionado nao tem CNPJ/CPF. Preencha o documento em "Editar dados nesta proposta".'
  }
  if (!htmlTemTexto(p.outrosItens)) {
    return 'Preencha "Outros Itens ou Serviços" — use o botao Aplicar modelo.'
  }
  return null
}
