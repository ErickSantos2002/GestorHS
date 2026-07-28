import { useEffect, useState } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Spinner } from '../../components/ui/Spinner'
import { ApiError } from '../../lib/api'
import { propostasApi } from './api'

export function VisualizarPropostaModal({ propostaId, propostaNumero, onClose }: {
  propostaId: number
  propostaNumero: number | null
  onClose: () => void
}) {
  const [url, setUrl] = useState<string | null>(null)
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    let objectUrl: string | null = null
    let cancelado = false
    propostasApi.baixarPdf(propostaId)
      .then((blob) => {
        if (cancelado) return
        objectUrl = URL.createObjectURL(blob)
        setUrl(objectUrl)
      })
      .catch((e) => { if (!cancelado) setErro(e instanceof ApiError ? e.message : 'Falha ao carregar o PDF') })
    return () => { cancelado = true; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [propostaId])

  return (
    <Modal open onClose={onClose} title={`Proposta${propostaNumero != null ? ` #${propostaNumero}` : ''}`} size="5xl">
      {erro ? (
        <p className="text-sm text-danger">{erro}</p>
      ) : !url ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : (
        <iframe src={url} title={`Proposta ${propostaNumero ?? ''}`} className="w-full h-[75vh] rounded-lg border border-border bg-white" />
      )}
    </Modal>
  )
}
