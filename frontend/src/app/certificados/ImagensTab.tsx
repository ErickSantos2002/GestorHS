import { useEffect, useState } from 'react'
import { certificadosApi, type ImagemCert } from './api'
import { Spinner } from '../../components/ui/Spinner'
import { useAuth } from '../../auth/AuthContext'
import { isAdmin } from '../../auth/roles'
import { ApiError } from '../../lib/api'

function apiBase(): string {
  const w = window as unknown as { __API_URL__?: string }
  const base = (w.__API_URL__ && w.__API_URL__.length ? w.__API_URL__ : (import.meta.env.VITE_API_URL ?? 'http://localhost:8000'))
  return base.replace(/\/$/, '')
}

export function ImagensTab() {
  const { user } = useAuth()
  const podeEditar = isAdmin(user) || user?.funcao === 'Laboratório'
  const [itens, setItens] = useState<ImagemCert[] | null>(null)
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [copiada, setCopiada] = useState<number | null>(null)

  function recarregar() {
    certificadosApi.listarImagens().then((r) => setItens(r.items)).catch(() => setItens([]))
  }
  useEffect(() => {
    recarregar()
  }, [])

  async function onEnviar(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setEnviando(true); setErro('')
    try {
      await certificadosApi.enviarImagem(file)
      recarregar()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao enviar imagem')
    } finally { setEnviando(false); e.target.value = '' }
  }

  async function onExcluir(id: number) {
    if (!window.confirm('Excluir esta imagem?')) return
    try { await certificadosApi.excluirImagem(id); recarregar() }
    catch { setErro('Falha ao excluir') }
  }

  async function copiar(img: ImagemCert) {
    const url = apiBase() + img.url
    try { await navigator.clipboard.writeText(url); setCopiada(img.id); setTimeout(() => setCopiada(null), 1500) } catch { /* ignore */ }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-slate-500">Imagens disponíveis para usar nos certificados (cole a URL no HTML do modelo).</p>
        {podeEditar && (
          <label className="cursor-pointer shrink-0">
            <span className="inline-flex items-center rounded-lg px-3 py-1.5 text-xs font-semibold bg-primary text-white hover:bg-primary-600 transition-colors">
              {enviando ? 'Enviando…' : 'Enviar imagem'}
            </span>
            <input type="file" accept="image/*" className="hidden" onChange={onEnviar} disabled={enviando} />
          </label>
        )}
      </div>
      {erro && <p className="text-sm text-danger">{erro}</p>}
      {itens === null ? <div className="py-10 flex justify-center"><Spinner className="w-7 h-7" /></div> : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhuma imagem.</p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
          {itens.map((img) => (
            <div key={img.id} className="rounded-xl border border-border bg-background-surface p-3 space-y-2">
              <img src={apiBase() + img.url} alt={img.nome ?? 'imagem'} className="w-full h-28 object-contain bg-white rounded-lg" />
              <p className="text-xs text-slate-300 truncate">{img.nome ?? img.arquivo}</p>
              <div className="flex gap-2 items-center">
                <button onClick={() => copiar(img)} className="text-xs text-primary hover:underline">{copiada === img.id ? 'Copiado!' : 'Copiar URL'}</button>
                {podeEditar && <button onClick={() => onExcluir(img.id)} className="text-xs text-danger hover:underline ml-auto">Excluir</button>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
