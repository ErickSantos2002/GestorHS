// Busca de dados publicos (CEP/CNPJ) para preencher o formulario de dados da
// empresa. A regra de QUAL campo cada busca preenche mora aqui, pura e testavel.

import { apiJson, ApiError } from '../../lib/api'
import type { CampoDados, DadosEmpresa } from './dadosEmpresa'

export interface ResultadoCep {
  cep: string
  endereco: string
  bairro: string
  municipio: string
  estado: string
}

export interface ResultadoCnpj extends ResultadoCep {
  documento: string
  nome: string
  numero: string
  complemento: string
  situacao: string
}

export const buscaApi = {
  cep: (cep: string) => apiJson<ResultadoCep>(`/integracoes/cep/${encodeURIComponent(cep)}`),
  cnpj: (cnpj: string) => apiJson<ResultadoCnpj>(`/integracoes/cnpj/${encodeURIComponent(cnpj)}`),
}

export interface Preenchimento {
  dados: DadosEmpresa
  preenchidos: CampoDados[]
}

/** Campo vazio na resposta nao apaga o que ja estava preenchido. */
function aplicar(dados: DadosEmpresa, valores: Partial<DadosEmpresa>): Preenchimento {
  const novo = { ...dados }
  const preenchidos: CampoDados[] = []
  for (const [campo, valor] of Object.entries(valores) as [CampoDados, string | undefined][]) {
    if (valor == null || valor.trim() === '') continue
    novo[campo] = valor
    preenchidos.push(campo)
  }
  return { dados: novo, preenchidos }
}

/** O CEP chega no nivel da rua — o numero continua sendo digitado a mao. */
export function aplicarResultadoCep(dados: DadosEmpresa, r: ResultadoCep): Preenchimento {
  return aplicar(dados, { cep: r.cep, endereco: r.endereco, bairro: r.bairro, municipio: r.municipio, estado: r.estado })
}

/**
 * Telefone e e-mail ficam de fora de proposito: na Receita costumam estar
 * desatualizados, e sao justamente os que a Health Safety tem bons no cadastro.
 */
export function aplicarResultadoCnpj(dados: DadosEmpresa, r: ResultadoCnpj): Preenchimento {
  return aplicar(dados, {
    nome: r.nome, cep: r.cep, endereco: r.endereco, numero: r.numero, complemento: r.complemento,
    bairro: r.bairro, municipio: r.municipio, estado: r.estado,
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
