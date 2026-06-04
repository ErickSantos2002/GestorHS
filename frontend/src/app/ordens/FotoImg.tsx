import { useEffect, useState } from 'react'
import { buscarBlobUrl } from './api'

export function FotoImg({ url, alt, className }: { url: string; alt: string; className?: string }) {
  const [src, setSrc] = useState<string | null>(null)
  useEffect(() => {
    let ativo = true
    let objectUrl: string | null = null
    buscarBlobUrl(url)
      .then((u) => { if (ativo) { objectUrl = u; setSrc(u) } else { URL.revokeObjectURL(u) } })
      .catch(() => { /* ignora; mostra placeholder */ })
    return () => { ativo = false; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [url])
  if (!src) return <div className={(className ?? '') + ' bg-background-elevated animate-pulse'} />
  return <img src={src} alt={alt} className={className} />
}
