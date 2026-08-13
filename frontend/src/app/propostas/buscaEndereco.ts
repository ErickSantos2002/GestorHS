// Busca de dados publicos (CEP/CNPJ) para preencher o override da proposta.
// A regra de QUAL campo cada busca preenche mora aqui, pura e testavel; o
// PropostaModal so orquestra a UI.

import { apiJson, ApiError } from '../../lib/api'
import type { CampoOverride } from './clienteOverride'

export interface ResultadoCep {
  cep: string
  endereco: string
  municipio: string
  estado: string
}

export interface ResultadoCnpj extends ResultadoCep {
  documento: string
  nome: string
  situacao: string
}

export const buscaApi = {
  cep: (cep: string) => apiJson<ResultadoCep>(`/integracoes/cep/${encodeURIComponent(cep)}`),
  cnpj: (cnpj: string) => apiJson<ResultadoCnpj>(`/integracoes/cnpj/${encodeURIComponent(cnpj)}`),
}

export type DraftOverride = Partial<Record<CampoOverride, string>>

export interface Preenchimento {
  draft: DraftOverride
  preenchidos: CampoOverride[]
}

/** Campo vazio na resposta nao apaga o que ja estava preenchido. */
function aplicar(draft: DraftOverride, valores: DraftOverride): Preenchimento {
  const novo = { ...draft }
  const preenchidos: CampoOverride[] = []
  for (const [campo, valor] of Object.entries(valores) as [CampoOverride, string | undefined][]) {
    if (valor == null || valor.trim() === '') continue
    novo[campo] = valor
    preenchidos.push(campo)
  }
  return { draft: novo, preenchidos }
}

/** O CEP chega no nivel da rua — o numero continua sendo digitado a mao. */
export function aplicarResultadoCep(draft: DraftOverride, r: ResultadoCep): Preenchimento {
  return aplicar(draft, { endereco: r.endereco, municipio: r.municipio, estado: r.estado })
}

/**
 * O CNPJ traz endereco completo (logradouro + numero + complemento).
 * Telefone e e-mail ficam de fora de proposito: na Receita costumam estar
 * desatualizados, e sao justamente os que a Health Safety tem bons no cadastro.
 */
export function aplicarResultadoCnpj(draft: DraftOverride, r: ResultadoCnpj): Preenchimento {
  return aplicar(draft, {
    nome: r.nome, endereco: r.endereco, municipio: r.municipio, estado: r.estado, cep: r.cep,
  })
}

export function mensagemErroBusca(e: unknown, tipo: 'CEP' | 'CNPJ'): string {
  if (e instanceof ApiError) {
    if (e.status === 404) return `${tipo} não encontrado.`
    if (e.status === 400) return `${tipo} inválido.`
    // Cota do provedor, contada pelo IP do servidor — ou seja, compartilhada por
    // todo mundo do sistema. Passa em segundos, e a mensagem precisa deixar claro
    // que e' so esperar, senao o usuario acha que a busca quebrou.
    if (e.status === 429) return `Muitas consultas de ${tipo} seguidas. Espere alguns segundos e tente de novo.`
    if (e.status === 502) return 'Serviço de consulta indisponível. Tente de novo em instantes.'
  }
  return `Falha ao consultar o ${tipo}.`
}
