import { type SelectHTMLAttributes } from 'react'
import { cn } from '../../lib/utils'
import { IconChevronDown } from './icons'

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
}

export function Select({ label, id, className, children, ...props }: SelectProps) {
  return (
    <div>
      {label && (
        <label htmlFor={id} className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">
          {label}
        </label>
      )}
      <div className="relative">
        <select
          id={id}
          className={cn(
            'appearance-none w-full pl-3 pr-8 py-2 text-sm rounded-lg border border-border bg-background-elevated',
            'text-slate-300 focus:outline-none focus:ring-2 focus:ring-primary/50 cursor-pointer transition-colors',
            className,
          )}
          {...props}
        >
          {children}
        </select>
        <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none">
          <IconChevronDown className="w-4 h-4" />
        </span>
      </div>
    </div>
  )
}
