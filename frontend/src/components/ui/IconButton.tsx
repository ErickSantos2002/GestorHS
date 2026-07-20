import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'

/** Tons das ações de tabela — a cor comunica a natureza da ação. */
const TONES = {
  editar: 'text-amber-400 bg-amber-400/10 border-amber-400/20 hover:text-amber-300 hover:bg-amber-400/20 hover:border-amber-400/40',
  ver: 'text-sky-400 bg-sky-400/10 border-sky-400/20 hover:text-sky-300 hover:bg-sky-400/20 hover:border-sky-400/40',
  excluir: 'text-danger bg-danger/10 border-danger/20 hover:text-red-400 hover:bg-danger/20 hover:border-danger/40',
  neutro: 'text-slate-400 bg-slate-400/10 border-slate-400/20 hover:text-slate-200 hover:bg-slate-400/20 hover:border-slate-400/40',
  ok: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20 hover:text-emerald-300 hover:bg-emerald-400/20 hover:border-emerald-400/40',
} as const

export type IconButtonTone = keyof typeof TONES

/** Botão só de ícone para colunas de ações. O `label` vira tooltip e nome acessível. */
export function IconButton({
  label,
  tone = 'neutro',
  onClick,
  children,
  className,
}: {
  label: string
  tone?: IconButtonTone
  onClick: () => void
  children: ReactNode
  className?: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      aria-label={label}
      className={cn(
        'inline-flex items-center justify-center p-1.5 rounded-lg border transition-colors',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40',
        TONES[tone],
        className,
      )}
    >
      {children}
    </button>
  )
}

/** Agrupa os IconButton de uma célula de ações. */
export function IconButtonGroup({ children }: { children: ReactNode }) {
  return <div className="flex items-center gap-1.5">{children}</div>
}
