import { useEffect, useState, type FormEvent } from 'react'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { ApiError } from '../../lib/api'
import { useCrud } from './useCrud'
import { equipamentosApi, categoriasApi, marcasApi, type Equipamento, type Categoria, type Marca, type EquipamentoPayload } from './api'

const VAZIO: EquipamentoPayload = {
  descricao: '', categoria: null, marca: null, detalhes: null, especificacao: null,
  preco_cod: 0, preco_por: 0, custo: 0, peso_calibragem: 0, peso: 0,
  estoque: 0, estoque_min: 0, ativo: false, destaque: false,
}

export function EquipamentosPanel() {
  const { itens, erro, setErro, recarregar } = useCrud<Equipamento>(equipamentosApi)
  const [categorias, setCategorias] = useState<Categoria[]>([])
  const [marcas, setMarcas] = useState<Marca[]>([])
  const [aberto, setAberto] = useState(false)
  const [editandoId, setEditandoId] = useState<number | null>(null)
  const [form, setForm] = useState<EquipamentoPayload>(VAZIO)
  const [erroForm, setErroForm] = useState('')
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void categoriasApi.listar().then(setCategorias).catch(() => setCategorias([]))
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void marcasApi.listar().then(setMarcas).catch(() => setMarcas([]))
  }, [])

  function nome(lista: { id: number; descricao: string | null }[], id: number | null) {
    return lista.find((x) => x.id === id)?.descricao ?? '—'
  }

  function set<K extends keyof EquipamentoPayload>(chave: K, valor: EquipamentoPayload[K]) {
    setForm((f) => ({ ...f, [chave]: valor }))
  }

  function abrirNovo() {
    setEditandoId(null); setForm(VAZIO); setErroForm(''); setAberto(true)
  }
  function abrirEdicao(e: Equipamento) {
    setEditandoId(e.id)
    setForm({
      descricao: e.descricao ?? '', categoria: e.categoria, marca: e.marca, detalhes: e.detalhes, especificacao: e.especificacao,
      preco_cod: e.preco_cod, preco_por: e.preco_por, custo: e.custo, peso_calibragem: e.peso_calibragem, peso: e.peso,
      estoque: e.estoque, estoque_min: e.estoque_min, ativo: e.ativo, destaque: e.destaque,
    })
    setErroForm(''); setAberto(true)
  }

  async function salvar(ev: FormEvent) {
    ev.preventDefault(); setErroForm(''); setEnviando(true)
    try {
      if (editandoId !== null) await equipamentosApi.atualizar(editandoId, form)
      else await equipamentosApi.criar(form)
      setAberto(false); await recarregar()
    } catch (err) {
      setErroForm(err instanceof ApiError ? err.message : 'Falha ao salvar')
    } finally {
      setEnviando(false)
    }
  }

  async function excluir(e: Equipamento) {
    if (!window.confirm(`Excluir "${e.descricao}"?`)) return
    try { await equipamentosApi.excluir(e.id); await recarregar() }
    catch (err) { setErro(err instanceof ApiError ? err.message : 'Falha ao excluir') }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-100">Catálogo de equipamentos</h2>
        <Button onClick={abrirNovo}>Novo</Button>
      </div>
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      {itens === null ? (
        <div className="flex justify-center py-10"><Spinner className="w-7 h-7" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum registro.</p>
      ) : (
        <Table head={<><TH>Descrição</TH><TH>Categoria</TH><TH>Marca</TH><TH>Preço</TH><TH>Estoque</TH><TH>Status</TH><TH>Ações</TH></>}>
          {itens.map((e) => (
            <tr key={e.id} className="hover:bg-background-elevated transition-colors">
              <TD>{e.descricao ?? '—'}</TD>
              <TD>{nome(categorias, e.categoria)}</TD>
              <TD>{nome(marcas, e.marca)}</TD>
              <TD>{e.preco_por.toFixed(2)}</TD>
              <TD>{e.estoque}</TD>
              <TD><Badge tone={e.ativo ? 'primary' : 'neutral'}>{e.ativo ? 'Ativo' : 'Inativo'}</Badge></TD>
              <TD>
                <div className="flex gap-3">
                  <button onClick={() => abrirEdicao(e)} className="text-xs text-primary hover:underline">Editar</button>
                  <button onClick={() => excluir(e)} className="text-xs text-danger hover:underline">Excluir</button>
                </div>
              </TD>
            </tr>
          ))}
        </Table>
      )}
      {aberto && (
        <Modal
          open
          onClose={() => setAberto(false)}
          title={editandoId !== null ? 'Editar — Equipamento' : 'Novo — Equipamento'}
          footer={
            <>
              <button type="button" onClick={() => setAberto(false)} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">Cancelar</button>
              <button type="submit" form="form-equip" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">Salvar</button>
            </>
          }
        >
          <form id="form-equip" className="space-y-4" onSubmit={salvar}>
            <Input id="e-descricao" label="Descrição" value={form.descricao ?? ''} onChange={(ev) => set('descricao', ev.target.value)} required />
            <div className="grid grid-cols-2 gap-3">
              <Select id="e-categoria" label="Categoria" value={form.categoria ? String(form.categoria) : ''} onChange={(ev) => set('categoria', ev.target.value ? Number(ev.target.value) : null)}>
                <option value="">— sem categoria —</option>
                {categorias.map((c) => <option key={c.id} value={c.id}>{c.descricao}</option>)}
              </Select>
              <Select id="e-marca" label="Marca" value={form.marca ? String(form.marca) : ''} onChange={(ev) => set('marca', ev.target.value ? Number(ev.target.value) : null)}>
                <option value="">— sem marca —</option>
                {marcas.map((m) => <option key={m.id} value={m.id}>{m.descricao}</option>)}
              </Select>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <Input id="e-preco_por" label="Preço" type="number" step="0.01" value={String(form.preco_por)} onChange={(ev) => set('preco_por', Number(ev.target.value))} />
              <Input id="e-custo" label="Custo" type="number" step="0.01" value={String(form.custo)} onChange={(ev) => set('custo', Number(ev.target.value))} />
              <Input id="e-preco_cod" label="Preço cod." type="number" step="0.01" value={String(form.preco_cod)} onChange={(ev) => set('preco_cod', Number(ev.target.value))} />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <Input id="e-estoque" label="Estoque" type="number" value={String(form.estoque)} onChange={(ev) => set('estoque', Number(ev.target.value))} />
              <Input id="e-estoque_min" label="Estoque mín." type="number" value={String(form.estoque_min)} onChange={(ev) => set('estoque_min', Number(ev.target.value))} />
              <Input id="e-peso" label="Peso" type="number" step="0.001" value={String(form.peso)} onChange={(ev) => set('peso', Number(ev.target.value))} />
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input type="checkbox" checked={form.ativo} onChange={(ev) => set('ativo', ev.target.checked)} className="accent-primary" />
              Ativo
            </label>
            {erroForm && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erroForm}</div>}
          </form>
        </Modal>
      )}
    </div>
  )
}
