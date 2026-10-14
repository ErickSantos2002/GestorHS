import { useCallback, useState } from 'react'

/** Quantidades de itens por página oferecidas nas listas paginadas. */
export const OPCOES_POR_PAGINA = [15, 25, 50, 100]

const chave = (tabela: string) => `gestorhs:porPagina:${tabela}`

/**
 * Itens por página escolhidos pelo usuário, guardados no navegador por tabela.
 * Valor guardado fora de OPCOES_POR_PAGINA é ignorado (cai no padrão).
 */
export function usePorPagina(tabela: string, padrao = 15) {
  const [porPagina, setEstado] = useState<number>(() => {
    try {
      const salvo = Number(localStorage.getItem(chave(tabela)))
      return OPCOES_POR_PAGINA.includes(salvo) ? salvo : padrao
    } catch {
      return padrao
    }
  })

  const setPorPagina = useCallback((n: number) => {
    setEstado(n)
    try {
      localStorage.setItem(chave(tabela), String(n))
    } catch {
      // localStorage indisponível (modo privado): segue só em memória
    }
  }, [tabela])

  return [porPagina, setPorPagina] as const
}
