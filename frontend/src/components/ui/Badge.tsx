import { type ReactNode } from 'react'
import { cn } from '../../lib/utils'

type Tone = 'primary' | 'danger' | 'warning' | 'info' | 'neutral'

const TONES: Record<Tone, string> = {
  primary: 'bg-primary/10 text-primary',
  danger: 'bg-danger/10 text-danger',
  warning: 'bg-warning/10 text-warning',
  info: 'bg-info/10 text-info',
  neutral: 'bg-slate-100 dark:bg-background-elevated text-slate-500',
}

export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span className={cn('inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full', TONES[tone])}>
      {children}
    </span>
  )
}
