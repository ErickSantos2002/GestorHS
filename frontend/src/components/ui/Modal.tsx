import { type ReactNode } from 'react'
import { IconX } from './icons'

type ModalSize = 'md' | 'lg' | 'xl'

const SIZES: Record<ModalSize, string> = {
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-xl',
}

interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  footer?: ReactNode
  size?: ModalSize
}

export function Modal({ open, onClose, title, children, footer, size = 'md' }: ModalProps) {
  if (!open) return null
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className={`w-full ${SIZES[size]} max-h-[90vh] flex flex-col rounded-2xl bg-background-surface border border-border shadow-2xl`}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-border shrink-0">
          <h2 className="text-base font-bold text-slate-100">{title}</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-200 hover:bg-background-elevated transition-colors"
            aria-label="Fechar"
          >
            <IconX className="w-4 h-4" />
          </button>
        </div>
        <div className="p-6 space-y-4 overflow-y-auto min-h-0">{children}</div>
        {footer && <div className="flex gap-2 px-6 pb-6 pt-1 shrink-0">{footer}</div>}
      </div>
    </div>
  )
}
