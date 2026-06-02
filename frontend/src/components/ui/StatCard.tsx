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
    <div className="rounded-xl bg-background-surface border border-border p-5 flex items-center gap-4">
      <div className={cn('w-12 h-12 rounded-xl flex items-center justify-center shrink-0', color)}>{icon}</div>
      <div className="min-w-0">
        <p className="text-2xl font-extrabold text-slate-100 leading-none">{value}</p>
        <p className="text-xs text-slate-500 mt-1 font-medium">{label}</p>
        {sub && <p className="text-[11px] text-slate-600 mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}
