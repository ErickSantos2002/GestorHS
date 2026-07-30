import { useEffect, useState } from 'react'
import { certificadosApi, CAMPOS_CERTIFICADO, type ModeloItem } from './api'
import { Spinner } from '../../components/ui/Spinner'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { SearchBar } from '../../components/ui/SearchBar'
import { Pagination } from '../../components/ui/Pagination'
import { usePaginacaoLocal } from '../../lib/usePaginacaoLocal'
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
  const [tipo, setTipo] = useState<'C' | 'M'>('C')
  const [texto, setTexto] = useState('')
  const [descricao, setDescricao] = useState('')
  const [carregandoEd, setCarregandoEd] = useState(false)
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState('')
  const { page, setPage, totalPages, total, pageSize, visiveis } = usePaginacaoLocal(itens, 15)

  useEffect(() => {
    let vivo = true
    certificadosApi.listarModelos({ q: busca || undefined })
      .then((r) => { if (vivo) setItens(r.items) })
      .catch(() => { if (vivo) setItens([]) })
    return () => { vivo = false }
  }, [busca])

  function carregar(equip: number, t: 'C' | 'M') {
    setCarregandoEd(true); setErro('')
    certificadosApi.obterModelo(equip, t)
      .then((c) => { setTexto(c.texto); setDescricao(c.descricao ?? '') })
      .catch(() => setErro('Falha ao carregar o certificado'))
      .finally(() => setCarregandoEd(false))
  }

  function abrir(m: ModeloItem) { setSelecionado(m); setTipo('C'); carregar(m.equipamento, 'C') }

  function trocarTipo(t: 'C' | 'M') { setTipo(t); if (selecionado) carregar(selecionado.equipamento, t) }

  async function salvar() {
    if (!selecionado) return
    setSalvando(true); setErro('')
    try {
      await certificadosApi.salvarModelo(selecionado.equipamento, { descricao: descricao.trim() || null, texto }, tipo)
      setItens((cur) => cur?.map((m) => m.equipamento === selecionado.equipamento
        ? { ...m, tem_calibracao: tipo === 'C' ? true : m.tem_calibracao, tem_manutencao: tipo === 'M' ? true : m.tem_manutencao }
        : m) ?? null)
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
          <div className="flex items-center gap-3">
            <div className="flex gap-1 rounded-lg bg-background-elevated p-1 w-fit">
              {(['C', 'M'] as const).map((t) => (
                <button key={t} type="button" onClick={() => trocarTipo(t)}
                  className={'px-3 py-1 text-xs rounded-md transition-colors ' + (tipo === t ? 'bg-primary text-white' : 'text-slate-400 hover:text-slate-200')}>
                  {t === 'C' ? 'Calibração' : 'Manutenção'}
                </button>
              ))}
            </div>
            {podeEditar && <Button onClick={salvar} disabled={salvando || carregandoEd}>{salvando ? 'Salvando…' : 'Salvar'}</Button>}
          </div>
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
      <SearchBar
        id="busca-modelo"
        value={q}
        onChange={setQ}
        onSubmit={(e) => { e.preventDefault(); setPage(1); setBusca(q.trim()) }}
        placeholder="Buscar modelo — ex.: Mark X"
      />
      {itens === null ? <div className="py-10 flex justify-center"><Spinner className="w-7 h-7" /></div> : (
        <div className="rounded-xl border border-border divide-y divide-border overflow-hidden">
          {visiveis.map((m) => (
            <button key={m.equipamento} onClick={() => abrir(m)}
              className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left hover:bg-background-elevated transition-colors">
              <span className="text-sm text-slate-200">{m.equipamento_descricao ?? `#${m.equipamento}`}</span>
              {m.tem_calibracao || m.tem_manutencao ? (
                <span className="flex gap-1.5">
                  {m.tem_calibracao && <Badge tone="primary">Calibração</Badge>}
                  {m.tem_manutencao && <Badge tone="info">Manutenção</Badge>}
                </span>
              ) : <Badge tone="neutral">Sem certificado</Badge>}
            </button>
          ))}
          {itens.length === 0 && <p className="px-4 py-8 text-center text-sm text-slate-500">Nenhum modelo.</p>}
        </div>
      )}
      {itens && total > 0 && (
        <Pagination page={page} totalPages={totalPages} total={total} pageSize={pageSize} onPageChange={setPage} itemLabel="modelos" />
      )}
    </div>
  )
}
