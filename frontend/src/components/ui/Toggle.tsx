import { cn } from '../../lib/utils'

interface ToggleProps {
  checked: boolean
  onChange: (next: boolean) => void
  label?: string
}

export function Toggle({ checked, onChange, label }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={cn('w-10 h-6 rounded-full transition-colors relative shrink-0', checked ? 'bg-primary' : 'bg-slate-200 dark:bg-border')}
    >
      <span className={cn('absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-transform', checked ? 'translate-x-5' : 'translate-x-1')} />
    </button>
  )
}
