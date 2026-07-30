import { cn } from '../../lib/utils'

const WINDOW_SIZE = 5

/** Janela deslizante de até WINDOW_SIZE páginas ao redor da página atual. */
function paginasVisiveis(atual: number, total: number): number[] {
  const metade = Math.floor(WINDOW_SIZE / 2)
  let inicio = Math.max(1, atual - metade)
  let fim = inicio + WINDOW_SIZE - 1
  if (fim > total) {
    fim = total
    inicio = Math.max(1, fim - WINDOW_SIZE + 1)
  }
  return Array.from({ length: fim - inicio + 1 }, (_, i) => inicio + i)
}

// Herdam automaticamente claro/escuro pelos tokens do tema (sem `dark:`).
const btnBase =
  'rounded-lg border border-border text-sm text-slate-300 transition-colors hover:bg-background-elevated ' +
  'disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40'

interface PaginationProps {
  /** Página atual (1-based). */
  page: number
  totalPages: number
  /** Total de itens (todas as páginas). */
  total: number
  /** Itens por página — usado para calcular "mostrando X a Y". */
  pageSize: number
  onPageChange: (page: number) => void
  /** Rótulo do que está sendo paginado. Ex.: "clientes", "propostas". */
  itemLabel?: string
}

/**
 * Paginação padrão do sistema: contagem "mostrando X a Y de Z" + navegação
 * com janela deslizante de páginas (desktop) e controle compacto (mobile).
 * Usa as cores do tema — funciona em claro e escuro sem ajustes.
 */
export function Pagination({ page, totalPages, total, pageSize, onPageChange, itemLabel = 'registros' }: PaginationProps) {
  const inicio = total === 0 ? 0 : (page - 1) * pageSize + 1
  const fim = Math.min(page * pageSize, total)
  const visiveis = paginasVisiveis(page, totalPages)
  const temPrev = page > 1
  const temNext = page < totalPages

  const contagem = (
    <span>
      Mostrando <span className="text-slate-300">{inicio}</span> a <span className="text-slate-300">{fim}</span> de{' '}
      <span className="text-slate-300">{total}</span> {itemLabel}
    </span>
  )

  // Uma única página: mantém a contagem, dispensa a navegação.
  if (totalPages <= 1) {
    return <div className="text-sm text-slate-400">{contagem}</div>
  }

  return (
    <div className="text-sm text-slate-400">
      {/* Desktop */}
      <div className="hidden items-center justify-between md:flex">
        {contagem}
        <div className="flex items-center gap-2">
          <button type="button" disabled={!temPrev} onClick={() => onPageChange(page - 1)} className={cn(btnBase, 'px-3 py-1.5')}>
            Anterior
          </button>
          <div className="flex gap-1">
            {visiveis.map((n) => (
              <button
                key={n}
                type="button"
                aria-current={n === page ? 'page' : undefined}
                onClick={() => onPageChange(n)}
                className={cn(
                  'min-w-9 rounded-lg px-2 py-1.5 text-sm transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40',
                  n === page
                    ? 'bg-primary font-semibold text-white'
                    : 'border border-border text-slate-300 hover:bg-background-elevated',
                )}
              >
                {n}
              </button>
            ))}
          </div>
          <button type="button" disabled={!temNext} onClick={() => onPageChange(page + 1)} className={cn(btnBase, 'px-3 py-1.5')}>
            Próxima
          </button>
        </div>
      </div>

      {/* Mobile */}
      <div className="flex flex-col items-center gap-2 md:hidden">
        {contagem}
        <div className="flex items-center justify-center gap-2">
          <button type="button" disabled={!temPrev} onClick={() => onPageChange(page - 1)} className={cn(btnBase, 'px-3 py-1.5')} aria-label="Página anterior">
            {'<'}
          </button>
          <span className="rounded-lg border border-border bg-background-elevated px-3 py-1.5 text-sm text-slate-200">
            {page} / {totalPages}
          </span>
          <button type="button" disabled={!temNext} onClick={() => onPageChange(page + 1)} className={cn(btnBase, 'px-3 py-1.5')} aria-label="Próxima página">
            {'>'}
          </button>
        </div>
      </div>
    </div>
  )
}

/**
 * Adaptador para as listas baseadas em `offset`/`limit`: converte para o modelo
 * de páginas do `Pagination` e devolve o novo offset ao mudar de página.
 */
export function PaginationOffset({ offset, limit, total, onOffsetChange, itemLabel }: {
  offset: number
  limit: number
  total: number
  onOffsetChange: (offset: number) => void
  itemLabel?: string
}) {
  const page = Math.floor(offset / limit) + 1
  const totalPages = Math.max(1, Math.ceil(total / limit))
  return (
    <Pagination
      page={page}
      totalPages={totalPages}
      total={total}
      pageSize={limit}
      onPageChange={(p) => onOffsetChange((p - 1) * limit)}
      itemLabel={itemLabel}
    />
  )
}
