import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'

/** Wrapper padrão de página: largura fluida com teto alto p/ ultrawide. */
export function PageContainer({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('mx-auto w-full max-w-[1700px] px-4 sm:px-6 lg:px-8 py-6 space-y-6', className)}>
      {children}
    </div>
  )
}

/** Grade de página de detalhe: principal (2/3) + lateral (1/3), reflui no xl. */
export function DetailGrid({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('grid grid-cols-1 xl:grid-cols-3 gap-6 items-start', className)}>
      {children}
    </div>
  )
}

/** Coluna principal do DetailGrid. */
export function DetailMain({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('xl:col-span-2 space-y-6 min-w-0', className)}>{children}</div>
}

/** Coluna lateral do DetailGrid. */
export function DetailAside({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('space-y-6 min-w-0', className)}>{children}</div>
}
