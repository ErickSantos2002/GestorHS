import { useEffect, useState, useCallback } from 'react'
import { buscarBlobUrl, type Foto } from './api'
import { IconX, IconChevronLeft, IconChevronRight } from '../../components/ui/icons'
import { Spinner } from '../../components/ui/Spinner'

export function FotoLightbox({ fotos, indiceInicial, onClose }: {
  fotos: Foto[]
  indiceInicial: number
  onClose: () => void
}) {
  const [indice, setIndice] = useState(indiceInicial)
  const [src, setSrc] = useState<string | null>(null)
  const total = fotos.length
  const foto = fotos[indice]

  const irPara = useCallback((delta: number) => {
    setIndice((i) => (i + delta + total) % total)
  }, [total])

  // teclado: Esc fecha, ← → navegam
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
      else if (e.key === 'ArrowLeft') irPara(-1)
      else if (e.key === 'ArrowRight') irPara(1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose, irPara])

  // carrega a imagem autenticada (blob) ao trocar de foto
  useEffect(() => {
    let ativo = true
    let objectUrl: string | null = null
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSrc(null)
    if (foto) {
      buscarBlobUrl(foto.url)
        .then((u) => { if (ativo) { objectUrl = u; setSrc(u) } else { URL.revokeObjectURL(u) } })
        .catch(() => { /* mostra spinner/erro silencioso */ })
    }
    return () => { ativo = false; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [foto])

  if (!foto) return null

  return (
    <div
      className="fixed inset-0 z-60 flex flex-col bg-black/85 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      {/* Topo: contador + fechar */}
      <div className="flex items-center justify-between px-5 py-4 text-slate-300 shrink-0">
        <span className="text-sm font-medium tabular-nums">{indice + 1} / {total}</span>
        <button
          type="button"
          onClick={onClose}
          aria-label="Fechar"
          className="p-2 rounded-lg text-slate-300 hover:text-white hover:bg-white/10 transition-colors"
        >
          <IconX className="w-5 h-5" />
        </button>
      </div>

      {/* Centro: imagem + setas */}
      <div
        className="relative flex-1 flex items-center justify-center px-4 min-h-0"
        onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
      >
        {total > 1 && (
          <button
            type="button"
            onClick={() => irPara(-1)}
            aria-label="Anterior"
            className="absolute left-2 sm:left-4 top-1/2 -translate-y-1/2 grid place-items-center w-11 h-11 rounded-full bg-white/10 text-white hover:bg-white/20 transition-colors focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <IconChevronLeft className="w-6 h-6" />
          </button>
        )}

        {src ? (
          <img
            src={src}
            alt={foto.legenda ?? 'Foto da OS'}
            className="max-h-full max-w-full object-contain rounded-lg shadow-2xl select-none"
          />
        ) : (
          <Spinner className="w-8 h-8 text-slate-400" />
        )}

        {total > 1 && (
          <button
            type="button"
            onClick={() => irPara(1)}
            aria-label="Próxima"
            className="absolute right-2 sm:right-4 top-1/2 -translate-y-1/2 grid place-items-center w-11 h-11 rounded-full bg-white/10 text-white hover:bg-white/20 transition-colors focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <IconChevronRight className="w-6 h-6" />
          </button>
        )}
      </div>

      {/* Legenda */}
      {foto.legenda && (
        <div className="shrink-0 px-5 py-4 text-center">
          <p className="text-sm text-slate-300">{foto.legenda}</p>
        </div>
      )}
    </div>
  )
}
