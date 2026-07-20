import { type ReactNode } from 'react'
import { cn } from '../../lib/utils'

interface StatCardProps {
  label: string
  value: ReactNode
  icon: ReactNode
  color: string
  sub?: string
}

export function StatCard({ label, value, icon, color, sub }: StatCardProps) {
  return (
    <div className="h-full rounded-2xl bg-background-surface border border-border p-7 flex items-center gap-5">
      <div className={cn('w-16 h-16 rounded-2xl flex items-center justify-center shrink-0', color)}>{icon}</div>
      <div className="min-w-0">
        <p className="text-4xl font-extrabold text-slate-100 leading-none">{value}</p>
        <p className="text-sm text-slate-500 mt-2 font-medium">{label}</p>
        {sub && <p className="text-xs text-slate-600 mt-1">{sub}</p>}
      </div>
    </div>
  )
}
