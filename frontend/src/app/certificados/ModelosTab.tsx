import { useEffect, useState } from 'react'
import { certificadosApi, CAMPOS_CERTIFICADO, type ModeloItem } from './api'
import { Spinner } from '../../components/ui/Spinner'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Badge } from '../../components/ui/Badge'
import { useAuth } from '../../auth/AuthContext'
import { isAdmin } from '../../auth/roles'
import { ApiError } from '../../lib/api'

export function ModelosTab() {
  const { user } = useAuth()
  const podeEditar = isAdmin(user) || user?.funcao === 'Laboratório'
  const [q, setQ] = useState('')
  const [busca, setBusca] = useState('')
  const [itens, setItens] = useState<ModeloItem[] | null>(null)
  const [selecionado, setSelecionado] = useState<ModeloItem | null>(null)
  const [texto, setTexto] = useState('')
  const [descricao, setDescricao] = useState('')
  const [carregandoEd, setCarregandoEd] = useState(false)
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState('')

  useEffect(() => {
    let vivo = true
    certificadosApi.listarModelos({ q: busca || undefined })
      .then((r) => { if (vivo) setItens(r.items) })
      .catch(() => { if (vivo) setItens([]) })
    return () => { vivo = false }
  }, [busca])

  function abrir(m: ModeloItem) {
    setSelecionado(m); setErro(''); setCarregandoEd(true)
    certificadosApi.obterModelo(m.equipamento)
      .then((c) => { setTexto(c.texto); setDescricao(c.descricao ?? '') })
      .catch(() => setErro('Falha ao carregar o certificado'))
      .finally(() => setCarregandoEd(false))
  }

  async function salvar() {
    if (!selecionado) return
    setSalvando(true); setErro('')
    try {
      await certificadosApi.salvarModelo(selecionado.equipamento, { descricao: descricao.trim() || null, texto })
      setItens((cur) => cur?.map((m) => m.equipamento === selecionado.equipamento ? { ...m, tem_certificado: true } : m) ?? null)
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao salvar')
    } finally { setSalvando(false) }
  }

  if (selecionado) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <button onClick={() => setSelecionado(null)} className="text-xs text-primary hover:underline">← Modelos</button>
            <h2 className="text-lg font-bold text-slate-100">{selecionado.equipamento_descricao}</h2>
          </div>
          {podeEditar && <Button onClick={salvar} disabled={salvando || carregandoEd}>{salvando ? 'Salvando…' : 'Salvar'}</Button>}
        </div>
        {erro && <p className="text-sm text-danger">{erro}</p>}
        <div className="flex flex-wrap gap-1.5">
          {CAMPOS_CERTIFICADO.map((c) => (
            <span key={c.campo} title={c.desc} className="rounded-full bg-background-elevated border border-border px-2 py-0.5 text-xs text-slate-400 font-mono">{c.campo}</span>
          ))}
        </div>
        {carregandoEd ? <div className="py-10 flex justify-center"><Spinner className="w-7 h-7" /></div> : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Input id="cert-desc" label="Descrição (opcional)" value={descricao} onChange={(e) => setDescricao(e.target.value)} />
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide">Código-fonte (HTML)</label>
              <textarea value={texto} onChange={(e) => setTexto(e.target.value)} readOnly={!podeEditar}
                className="w-full h-[60vh] px-3 py-2 text-xs font-mono rounded-lg border border-border bg-background-elevated text-slate-200 focus:outline-none focus:ring-2 focus:ring-primary/50" />
            </div>
            <div className="space-y-2">
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide">Pré-visualização</label>
              <iframe title="preview" sandbox="" srcDoc={texto} className="w-full h-[60vh] rounded-lg border border-border bg-white" />
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <form onSubmit={(e) => { e.preventDefault(); setBusca(q.trim()) }} className="flex gap-2 items-end">
        <Input id="busca-modelo" label="Buscar modelo" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ex.: Mark X" />
        <Button type="submit" variant="secondary">Buscar</Button>
      </form>
      {itens === null ? <div className="py-10 flex justify-center"><Spinner className="w-7 h-7" /></div> : (
        <div className="rounded-xl border border-border divide-y divide-border overflow-hidden">
          {itens.map((m) => (
            <button key={m.equipamento} onClick={() => abrir(m)}
              className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left hover:bg-background-elevated transition-colors">
              <span className="text-sm text-slate-200">{m.equipamento_descricao ?? `#${m.equipamento}`}</span>
              <Badge tone={m.tem_certificado ? 'primary' : 'neutral'}>{m.tem_certificado ? 'Com certificado' : 'Sem certificado'}</Badge>
            </button>
          ))}
          {itens.length === 0 && <p className="px-4 py-8 text-center text-sm text-slate-500">Nenhum modelo.</p>}
        </div>
      )}
    </div>
  )
}
