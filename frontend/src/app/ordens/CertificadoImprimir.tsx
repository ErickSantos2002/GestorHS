import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { ordensApi, type OSCertificado } from './api'

export function CertificadoImprimir() {
  const { id, tipo } = useParams()
  const [cert, setCert] = useState<OSCertificado | null | undefined>(undefined)
  useEffect(() => {
    ordensApi.certificados(Number(id))
      .then((cs) => setCert(cs.find((c) => c.tipo === tipo) ?? null))
      .catch(() => setCert(null))
  }, [id, tipo])
  useEffect(() => {
    if (cert?.html) {
      const t = setTimeout(() => window.print(), 400)
      return () => clearTimeout(t)
    }
  }, [cert])
  if (cert === undefined) return <p style={{ padding: 24 }}>Carregando…</p>
  if (!cert || !cert.html) return <p style={{ padding: 24 }}>Certificado não encontrado.</p>
  return <div style={{ background: '#fff', color: '#000' }} dangerouslySetInnerHTML={{ __html: cert.html }} />
}
