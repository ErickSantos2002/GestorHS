/** Valor em reais no formato brasileiro, sem o símbolo: 1234.5 -> "1.234,50".
 *
 * Estava copiado em cada tela de proposta; vive aqui para o bloco da proposta na
 * caixa mostrar exatamente o mesmo número que a tela de Propostas. */
export function formatarMoeda(v: number): string {
  return v.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
