import { useEffect } from 'react'
import { Badge } from '../../components/ui/Badge'
import { IconX } from '../../components/ui/icons'
import { CHANGELOG, TIPO_MUDANCA } from './data'

export function ChangelogModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  useEffect(() => {
    if (!open) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="w-full max-w-3xl max-h-[90vh] flex flex-col rounded-2xl bg-background-surface border border-border shadow-2xl">
        <div className="flex items-start justify-between px-7 py-5 border-b border-border shrink-0">
          <div>
            <h2 className="text-lg font-bold text-slate-100">O que há de novo?</h2>
            <p className="text-sm text-slate-500 mt-0.5">Atualizações recentes do GestorHS</p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-200 hover:bg-background-elevated transition-colors"
            aria-label="Fechar"
          >
            <IconX className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-7 py-6 space-y-7">
          {CHANGELOG.map((v, idx) => (
            <section key={v.versao} className="space-y-3">
              <div className="flex items-center gap-2.5">
                <Badge tone="primary">v{v.versao}</Badge>
                <span className="text-xs text-slate-500">{v.data}</span>
                {idx === 0 && <Badge tone="primary">Versão atual</Badge>}
              </div>
              <div className="space-y-2">
                {v.itens.map((item, i) => {
                  const meta = TIPO_MUDANCA[item.tipo]
                  return (
                    <div key={i} className="flex gap-4 rounded-xl bg-background-elevated border border-border px-4 py-3.5">
                      <div className="shrink-0 pt-0.5">
                        <Badge tone={meta.tone}>{meta.label}</Badge>
                      </div>
                      <p className="text-sm text-slate-300 leading-relaxed">{item.texto}</p>
                    </div>
                  )
                })}
              </div>
            </section>
          ))}
        </div>

        <div className="px-7 py-4 border-t border-border shrink-0">
          <p className="text-center text-xs text-slate-600">GestorHS — desenvolvido internamente pela equipe</p>
        </div>
      </div>
    </div>
  )
}
