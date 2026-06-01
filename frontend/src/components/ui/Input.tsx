import { type InputHTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
}

export function Input({ label, id, className, ...props }: InputProps) {
  return (
    <div>
      {label && (
        <label htmlFor={id} className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">
          {label}
        </label>
      )}
      <input
        id={id}
        className={cn(
          'w-full px-3 py-2.5 text-sm rounded-lg border border-border bg-background-elevated',
          'text-slate-100 placeholder-slate-500',
          'focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-colors',
          className,
        )}
        {...props}
      />
    </div>
  )
}
