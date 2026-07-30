import { useState } from 'react'

/**
 * Paginação no cliente: fatia uma lista já carregada em páginas de `pageSize`.
 * Devolve os itens da página atual e as props para o `<Pagination>`.
 * A página é normalizada na leitura — se a lista encolher (filtro/exclusão),
 * `page` nunca aponta além do total. Reinicie com `setPage(1)` ao trocar filtro.
 */
export function usePaginacaoLocal<T>(itens: T[] | null | undefined, pageSize = 15) {
  const [page, setPage] = useState(1)
  const total = itens?.length ?? 0
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const pageAtual = Math.min(page, totalPages)
  const visiveis = itens ? itens.slice((pageAtual - 1) * pageSize, pageAtual * pageSize) : []
  return { page: pageAtual, setPage, totalPages, total, pageSize, visiveis }
}
