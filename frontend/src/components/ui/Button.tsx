import { type ButtonHTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost'

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-primary text-white hover:bg-primary-600',
  secondary: 'border border-border text-slate-300 hover:bg-background-elevated',
  danger: 'bg-danger text-white hover:bg-danger-600',
  ghost: 'text-slate-400 hover:text-slate-100 hover:bg-background-elevated',
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
}

export function Button({ variant = 'primary', className, ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        'flex items-center justify-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg',
        'active:scale-95 transition-all duration-150',
        'disabled:opacity-60 disabled:cursor-not-allowed',
        VARIANTS[variant],
        className,
      )}
      {...props}
    />
  )
}
