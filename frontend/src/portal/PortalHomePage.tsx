import { useEffect, useState } from 'react'
import { Spinner } from '../components/ui/Spinner'
import { ApiError } from '../lib/api'
import { usePortalAuth } from './PortalAuthContext'
import { portalApi, type PortalResumo } from './api'

function Cartao({ titulo, valor, destaque }: { titulo: string; valor: number; destaque?: boolean }) {
  return (
    <div className="rounded-2xl bg-background-surface border border-border p-5">
      <p className="text-xs text-slate-500 uppercase tracking-wide">{titulo}</p>
      <p className={destaque ? 'text-3xl font-extrabold text-danger mt-1' : 'text-3xl font-extrabold text-slate-100 mt-1'}>{valor}</p>
    </div>
  )
}

export function PortalHomePage() {
  const { cliente } = usePortalAuth()
  const [resumo, setResumo] = useState<PortalResumo | null>(null)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let ativo = true
    portalApi.resumo()
      .then((r) => { if (ativo) setResumo(r) })
      .catch((e) => { if (ativo) setErro(e instanceof ApiError ? e.message : 'Falha ao carregar') })
    return () => { ativo = false }
  }, [])

  return (
    <div className="px-4 md:px-6 py-6 space-y-6">
      <h1 className="text-2xl font-extrabold text-slate-100">Olá, {cliente?.cliente_nome ?? 'cliente'}</h1>
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      {resumo === null && !erro ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : resumo ? (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 max-w-2xl">
          <Cartao titulo="Aparelhos" valor={resumo.aparelhos} />
          <Cartao titulo="Vencidos" valor={resumo.vencidos} destaque={resumo.vencidos > 0} />
          <Cartao titulo="OS em andamento" valor={resumo.os_andamento} />
        </div>
      ) : null}
    </div>
  )
}
