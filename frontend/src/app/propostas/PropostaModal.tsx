import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { IconButton } from '../../components/ui/IconButton'
import { IconSearch, IconPlus, IconTrash, IconX, IconPencil, IconClientes, IconFrota, IconTag, IconNote } from '../../components/ui/icons'
import { RichText } from '../../components/ui/RichText'
import { useAuth } from '../../auth/AuthContext'
import { ApiError } from '../../lib/api'
import { hojeISO } from '../../lib/datas'
import { formatarDocumento } from '../../lib/documento'
import { descreverVencimento } from './aparelhosFrota'
import { clientesApi, type Cliente, type ClienteListItem } from '../clientes/api'
import { STATUS_CALIBRACAO, type StatusCalibracao } from '../frota/api'
import {
  propostasApi, frotaDoCliente, servicosApi, produtosApi,
  type PropostaCreate, type PropostaItemCreate, type EquipamentoClienteFrota,
} from './api'
import { buildDefaultOtherItems, buildPhoebusOtherItems, DEFAULT_NOTES } from './propostaDefaults'

const UFS = [
  'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 'MG',
  'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO',
]

// Chaves PT-BR do override editável só nesta proposta — DEVEM bater com o
// backend (ver app/core/proposta_pdf.py, montagem do contexto do certificado/PDF).
const CAMPOS_OVERRIDE = ['nome', 'documento', 'endereco', 'municipio', 'estado', 'email', 'telefone', 'contato'] as const
type CampoOverride = (typeof CAMPOS_OVERRIDE)[number]

const formatarMoeda = (v: number) => v.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const sanitizarDecimal = (v: string) => v.replace(/[^0-9,]/g, '').replace(/(,.*),/g, '$1')
const converterDecimal = (v: string) => parseFloat(v.replace(',', '.')) || 0
const numeroParaTexto = (n?: number | null) => (n ? String(n).replace('.', ',') : '')

const ITEM_VAZIO = (): PropostaItemCreate => ({ descricao: '', sku: '', quantidade: 1, unidade: 'Unid', preco_un: 0 })

const EMPTY_FORM = (): PropostaCreate => ({
  cliente: null,
  contato: '',
  vendedor: '',
  data: '',
  intro: '',
  outros_itens: '',
  desconto: 0,
  frete: 0,
  forma_envio: '',
  forma_frete: '',
  transportador: '',
  condicao_pagamento: '',
  validade_dias: 30,
  data_entrega: '',
  descricao_entrega: '',
  endereco_entrega_diferente: false,
  endereco_entrega: null,
  cliente_override: null,
  observacoes: '',
  assinatura: '',
  itens: [],
  aparelhos: [],
})

function overrideTemDados(o?: Record<string, unknown> | null): boolean {
  return !!o && Object.values(o).some((v) => v != null && String(v).trim() !== '')
}

function Secao({ titulo, icon, primeira, children }: { titulo: string; icon?: ReactNode; primeira?: boolean; children: ReactNode }) {
  return (
    <section className={primeira ? 'space-y-4' : 'space-y-4 border-t border-border pt-6'}>
      <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
        {icon}
        {titulo}
      </div>
      {children}
    </section>
  )
}

const inputClass = 'w-full px-3 py-2 text-sm rounded-lg border border-border bg-background-elevated text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-transparent transition-colors'

interface ItemCatalogo { nome: string; sku: string | null; preco: number }

export function PropostaModal({ propostaId, onClose, onSalvo }: {
  propostaId?: number | null
  onClose: () => void
  onSalvo?: (id: number) => void
}) {
  const { user } = useAuth()
  const editando = propostaId != null

  const [form, setForm] = useState<PropostaCreate>(EMPTY_FORM())
  const [itens, setItens] = useState<PropostaItemCreate[]>([])
  const [descontoStr, setDescontoStr] = useState('')
  const [freteStr, setFreteStr] = useState('')
  const [numero, setNumero] = useState<number | null>(null)
  const [editorKey, setEditorKey] = useState(0)
  const [modeloTexto, setModeloTexto] = useState<'demais' | 'phoebus'>('demais')

  const [carregando, setCarregando] = useState(editando)
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState('')

  // ─── Cliente ──────────────────────────────────────────────────────────
  const [clienteSelecionado, setClienteSelecionado] = useState<Cliente | null>(null)
  const [clienteBusca, setClienteBusca] = useState('')
  const [resultadosCliente, setResultadosCliente] = useState<ClienteListItem[]>([])
  const [buscandoCliente, setBuscandoCliente] = useState(false)
  const clienteAnteriorRef = useRef<number | null>(null)

  // ─── Frota / Aparelhos ────────────────────────────────────────────────
  const [frota, setFrota] = useState<EquipamentoClienteFrota[] | null>(null)
  const [carregandoFrota, setCarregandoFrota] = useState(false)
  const [aparelhosSelecionados, setAparelhosSelecionados] = useState<number[]>([])
  const [buscaAparelho, setBuscaAparelho] = useState('')

  // ─── Override cliente/pessoa (só nesta proposta) ──────────────────────
  const [mostrarOverride, setMostrarOverride] = useState(false)
  const [overrideDraft, setOverrideDraft] = useState<Partial<Record<CampoOverride, string>>>({})

  // ─── Catálogo (Serviços + Produtos) para busca por linha de item ──────
  // A própria Descrição é a busca: digitar já filtra o catálogo; não existe
  // descrição manual — o dropdown escapa do overflow da Modal via portal.
  const [catalogo, setCatalogo] = useState<{ servicos: ItemCatalogo[]; produtos: ItemCatalogo[] } | null>(null)
  const [linhaAberta, setLinhaAberta] = useState<number | null>(null)
  const [posDropdown, setPosDropdown] = useState<{ top: number; left: number; width: number } | null>(null)
  const descricaoRefs = useRef<Record<number, HTMLInputElement | null>>({})
  const dropdownRef = useRef<HTMLDivElement | null>(null)

  function setField<K extends keyof PropostaCreate>(key: K, value: PropostaCreate[K]) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  // ─── Carrega catálogo uma vez ──────────────────────────────────────────
  useEffect(() => {
    Promise.all([servicosApi.listar(), produtosApi.listar()])
      .then(([servicos, produtos]) => {
        setCatalogo({
          servicos: servicos.map((s) => ({ nome: s.nome, sku: s.sku, preco: s.preco })),
          produtos: produtos.map((p) => ({ nome: p.nome, sku: p.sku, preco: p.preco })),
        })
      })
      .catch(() => setCatalogo({ servicos: [], produtos: [] }))
  }, [])

  // ─── Carrega proposta existente (edição) ──────────────────────────────
  useEffect(() => {
    if (!propostaId) return
    let vivo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCarregando(true)
    propostasApi.obter(propostaId)
      .then((p) => {
        if (!vivo) return
        setForm({
          cliente: p.cliente,
          contato: p.contato ?? '',
          vendedor: p.vendedor ?? '',
          data: p.data ?? '',
          intro: p.intro ?? '',
          outros_itens: p.outros_itens ?? '',
          desconto: p.desconto ?? 0,
          frete: p.frete ?? 0,
          forma_envio: p.forma_envio ?? '',
          forma_frete: p.forma_frete ?? '',
          transportador: p.transportador ?? '',
          condicao_pagamento: p.condicao_pagamento ?? '',
          validade_dias: p.validade_dias ?? null,
          data_entrega: p.data_entrega ?? '',
          descricao_entrega: p.descricao_entrega ?? '',
          endereco_entrega_diferente: p.endereco_entrega_diferente ?? false,
          endereco_entrega: p.endereco_entrega ?? null,
          cliente_override: p.cliente_override ?? null,
          observacoes: p.observacoes ?? '',
          assinatura: p.assinatura ?? '',
          itens: [],
          aparelhos: [],
        })
        setItens(p.itens.map((i) => ({ descricao: i.descricao, sku: i.sku, quantidade: i.quantidade, unidade: i.unidade, preco_un: i.preco_un })))
        setAparelhosSelecionados(p.aparelhos.map((a) => a.equipamento_cliente).filter((x): x is number => x != null))
        setDescontoStr(numeroParaTexto(p.desconto))
        setFreteStr(numeroParaTexto(p.frete))
        setNumero(p.numero)
        setEditorKey((k) => k + 1)
      })
      .catch(() => { if (vivo) setErro('Falha ao carregar a proposta') })
      .finally(() => { if (vivo) setCarregando(false) })
    return () => { vivo = false }
  }, [propostaId])

  // ─── Defaults de proposta nova ────────────────────────────────────────
  useEffect(() => {
    if (propostaId) return
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setForm((f) => ({
      ...f,
      data: f.data || hojeISO(),
      vendedor: user?.nome ?? '',
      assinatura: f.assinatura || `Atenciosamente,\n${user?.nome ?? ''}`,
      observacoes: f.observacoes || DEFAULT_NOTES,
    }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ─── Busca de cliente ──────────────────────────────────────────────────
  useEffect(() => {
    if (clienteSelecionado || !clienteBusca.trim()) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setResultadosCliente([])
      return
    }
    let vivo = true
    setBuscandoCliente(true)
    clientesApi.listar({ q: clienteBusca.trim(), limit: 20 })
      .then((r) => { if (vivo) setResultadosCliente(r.items) })
      .catch(() => { if (vivo) setResultadosCliente([]) })
      .finally(() => { if (vivo) setBuscandoCliente(false) })
    return () => { vivo = false }
  }, [clienteBusca, clienteSelecionado])

  // ─── Carrega dados completos do cliente + frota ao trocar `form.cliente` ──
  useEffect(() => {
    const trocouDeCliente = clienteAnteriorRef.current !== null && clienteAnteriorRef.current !== form.cliente
    clienteAnteriorRef.current = form.cliente
    if (trocouDeCliente) {
      setAparelhosSelecionados([])
      setBuscaAparelho('')
    }

    if (form.cliente == null) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setClienteSelecionado(null)
      setFrota(null)
      return
    }
    let vivo = true
    setCarregandoFrota(true)
    const clienteId = form.cliente
    Promise.all([
      clientesApi.obter(clienteId).catch(() => null),
      frotaDoCliente(clienteId).catch(() => []),
    ]).then(([cli, itensFrota]) => {
      if (!vivo) return
      setClienteSelecionado(cli)
      setFrota(itensFrota)
      setCarregandoFrota(false)
      if (cli?.contato) {
        setForm((f) => (f.contato ? f : { ...f, contato: cli.contato ?? '' }))
      }
    })
    return () => { vivo = false }
  }, [form.cliente])

  // ─── Detecção heurística de Phoebus entre os aparelhos marcados ───────
  useEffect(() => {
    if (!frota) return
    const marcados = frota.filter((a) => aparelhosSelecionados.includes(a.id))
    if (marcados.length && marcados.some((a) => /phoebus/i.test(a.equipamento_descricao ?? ''))) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setModeloTexto('phoebus')
    }
  }, [aparelhosSelecionados, frota])

  // ─── Fecha o dropdown do catálogo ao clicar fora ou apertar Esc ───────
  useEffect(() => {
    if (linhaAberta === null) return
    function aoClicarFora(e: MouseEvent) {
      const alvo = e.target as Node
      const dentroDropdown = dropdownRef.current?.contains(alvo)
      const dentroInput = linhaAberta !== null && descricaoRefs.current[linhaAberta]?.contains(alvo)
      if (!dentroDropdown && !dentroInput) setLinhaAberta(null)
    }
    function aoTeclar(e: KeyboardEvent) {
      if (e.key === 'Escape') setLinhaAberta(null)
    }
    document.addEventListener('mousedown', aoClicarFora)
    document.addEventListener('keydown', aoTeclar)
    return () => {
      document.removeEventListener('mousedown', aoClicarFora)
      document.removeEventListener('keydown', aoTeclar)
    }
  }, [linhaAberta])

  // ─── Cliente handlers ──────────────────────────────────────────────────
  function selecionarCliente(c: ClienteListItem) {
    setField('cliente', c.id)
    setClienteBusca('')
    setResultadosCliente([])
  }

  function removerCliente() {
    setField('cliente', null)
    setClienteBusca('')
    setResultadosCliente([])
  }

  // ─── Override ──────────────────────────────────────────────────────────
  const temOverride = overrideTemDados(form.cliente_override)

  function abrirOverride() {
    const atual = form.cliente_override
    if (overrideTemDados(atual)) {
      const draft: Partial<Record<CampoOverride, string>> = {}
      CAMPOS_OVERRIDE.forEach((k) => { draft[k] = String(atual?.[k] ?? '') })
      setOverrideDraft(draft)
    } else {
      setOverrideDraft({
        nome: clienteSelecionado?.nome ?? '',
        documento: clienteSelecionado?.cgc || clienteSelecionado?.cpf || '',
        endereco: clienteSelecionado?.endereco ?? '',
        municipio: clienteSelecionado?.municipio ?? '',
        estado: clienteSelecionado?.estado ?? '',
        email: clienteSelecionado?.email ?? '',
        telefone: clienteSelecionado?.celular || clienteSelecionado?.whatsapp || clienteSelecionado?.telefones || '',
        contato: form.contato ?? '',
      })
    }
    setMostrarOverride(true)
  }

  function definirOverride(campo: CampoOverride, valor: string) {
    setOverrideDraft((d) => ({ ...d, [campo]: valor }))
  }

  function salvarOverride() {
    const limpo: Record<string, string> = {}
    CAMPOS_OVERRIDE.forEach((k) => {
      const v = overrideDraft[k]
      if (v != null && v.trim() !== '') limpo[k] = v.trim()
    })
    setField('cliente_override', Object.keys(limpo).length ? limpo : null)
    setMostrarOverride(false)
  }

  function restaurarOverride() {
    setField('cliente_override', null)
    setMostrarOverride(false)
  }

  // ─── Aparelhos ─────────────────────────────────────────────────────────
  function toggleAparelho(id: number) {
    setAparelhosSelecionados((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]))
  }

  // ─── Outros itens (bloco técnico) ─────────────────────────────────────
  function aplicarModeloTexto() {
    const marcados = (frota ?? []).filter((a) => aparelhosSelecionados.includes(a.id))
    const modelos = Array.from(new Set(marcados.map((a) => a.equipamento_descricao).filter((v): v is string => !!v)))
    const series = Array.from(new Set(marcados.map((a) => a.serie).filter((v): v is string => !!v)))
    const texto = modeloTexto === 'phoebus'
      ? buildPhoebusOtherItems(series.join(', '), '')
      : buildDefaultOtherItems(modelos.join(', '), series.join(', '))
    setField('outros_itens', texto)
    setEditorKey((k) => k + 1)
  }

  // ─── Itens ─────────────────────────────────────────────────────────────
  function adicionarItem() {
    setItens((cur) => [...cur, ITEM_VAZIO()])
  }

  function removerItem(idx: number) {
    setItens((cur) => cur.filter((_, i) => i !== idx))
    setLinhaAberta(null)
  }

  function atualizarItem<K extends keyof PropostaItemCreate>(idx: number, campo: K, valor: PropostaItemCreate[K]) {
    setItens((cur) => cur.map((it, i) => (i === idx ? { ...it, [campo]: valor } : it)))
  }

  function resultadosParaLinha(idx: number): ItemCatalogo[] {
    const q = (itens[idx]?.descricao ?? '').trim().toLowerCase()
    if (!q || !catalogo) return []
    const todos = [...catalogo.servicos, ...catalogo.produtos]
    return todos.filter((t) => t.nome.toLowerCase().includes(q) || (t.sku ?? '').toLowerCase().includes(q)).slice(0, 20)
  }

  function abrirBuscaCatalogo(idx: number) {
    setLinhaAberta(idx)
    const el = descricaoRefs.current[idx]
    if (el) {
      const r = el.getBoundingClientRect()
      setPosDropdown({ top: r.bottom + 4, left: r.left, width: r.width })
    }
  }

  function selecionarItemCatalogo(idx: number, item: ItemCatalogo) {
    atualizarItem(idx, 'descricao', item.nome)
    atualizarItem(idx, 'sku', item.sku ?? '')
    atualizarItem(idx, 'preco_un', item.preco)
    setLinhaAberta(null)
  }

  // ─── Totais ────────────────────────────────────────────────────────────
  const totalItens = itens.reduce((soma, i) => soma + (Number(i.quantidade) || 0) * (Number(i.preco_un) || 0), 0)
  const totalProposta = totalItens + (Number(form.frete) || 0) - (Number(form.desconto) || 0)

  // ─── Submit ────────────────────────────────────────────────────────────
  async function submeter(e: FormEvent) {
    e.preventDefault()
    setErro('')
    setSalvando(true)
    try {
      const limparData = (d?: string | null) => (d && d.trim() ? d : null)
      const payload: PropostaCreate = {
        ...form,
        data: limparData(form.data),
        data_entrega: limparData(form.data_entrega),
        desconto: Number(form.desconto) || 0,
        frete: Number(form.frete) || 0,
        validade_dias: form.validade_dias ? Number(form.validade_dias) : null,
        endereco_entrega: form.endereco_entrega_diferente ? (form.endereco_entrega ?? null) : null,
        cliente_override: form.cliente_override ?? null,
        itens: itens.map((i) => ({ ...i, quantidade: Number(i.quantidade) || 0, preco_un: Number(i.preco_un) || 0 })),
        aparelhos: aparelhosSelecionados.map((id) => ({ equipamento_cliente: id })),
      }
      const salvo = editando && propostaId
        ? await propostasApi.atualizar(propostaId, payload)
        : await propostasApi.criar(payload)
      onSalvo?.(salvo.id)
      onClose()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao salvar a proposta')
    } finally {
      setSalvando(false)
    }
  }

  const enderecoEntregaTexto = (form.endereco_entrega as { texto?: string } | null)?.texto ?? ''

  return (
    <Modal
      open
      onClose={onClose}
      title={editando ? `Editar Proposta${numero != null ? ` #${numero}` : ''}` : 'Nova Proposta'}
      size="5xl"
      footer={
        <>
          <Button variant="secondary" type="button" onClick={onClose} disabled={salvando}>Cancelar</Button>
          <Button type="submit" form="form-proposta" disabled={salvando || carregando}>
            {salvando ? 'Salvando…' : editando ? 'Salvar Alterações' : 'Criar Proposta'}
          </Button>
        </>
      }
    >
      {carregando ? (
        <div className="flex justify-center py-16"><Spinner className="w-8 h-8" /></div>
      ) : (
        <form id="form-proposta" onSubmit={submeter} className="space-y-6">

          {/* ── Cliente ── */}
          <Secao titulo="Cliente" icon={<IconClientes className="w-3.5 h-3.5" />} primeira>
            <div>
              <label className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Empresa / Cliente</label>
              {clienteSelecionado ? (
                <div className="flex items-start justify-between gap-3 rounded-lg border border-primary/40 bg-primary/10 p-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-semibold text-slate-100">{clienteSelecionado.nome}</p>
                    {(clienteSelecionado.cgc || clienteSelecionado.cpf) && (
                      <p className="mt-0.5 text-xs text-slate-400">CNPJ/CPF: {formatarDocumento(clienteSelecionado.cgc || clienteSelecionado.cpf)}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <IconButton label="Editar dados nesta proposta" tone="editar" onClick={abrirOverride}><IconPencil className="w-4 h-4" /></IconButton>
                    <IconButton label="Remover empresa" tone="excluir" onClick={removerCliente}><IconX className="w-4 h-4" /></IconButton>
                  </div>
                </div>
              ) : (
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none"><IconSearch className="w-4 h-4" /></span>
                  <input
                    value={clienteBusca}
                    onChange={(e) => setClienteBusca(e.target.value)}
                    placeholder="Buscar cliente por nome, CNPJ ou CPF"
                    className={`pl-9 ${inputClass}`}
                  />
                  {buscandoCliente && <p className="mt-1 text-xs text-slate-500">Buscando…</p>}
                  {resultadosCliente.length > 0 && (
                    <ul className="mt-1.5 divide-y divide-border rounded-lg border border-border overflow-hidden max-h-52 overflow-y-auto">
                      {resultadosCliente.map((c) => (
                        <li key={c.id}>
                          <button type="button" onClick={() => selecionarCliente(c)} className="w-full text-left px-3 py-2.5 text-sm hover:bg-background-elevated transition-colors">
                            <span className="block font-semibold text-slate-200">{c.nome ?? `Cliente #${c.id}`}</span>
                            {(c.cgc || c.cpf) && <span className="block text-xs text-slate-500">{formatarDocumento(c.cgc || c.cpf)}</span>}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>

            <Input
              id="contato-proposta"
              label="Aos cuidados de (contato)"
              value={form.contato ?? ''}
              onChange={(e) => setField('contato', e.target.value)}
              placeholder="Nome do contato no cliente"
            />

            {temOverride && (
              <p className="text-xs font-medium text-warning">Dados do cliente/contato editados só nesta proposta.</p>
            )}

            {mostrarOverride && (
              <div className="space-y-3 rounded-lg border border-warning/40 bg-warning/5 p-4">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold uppercase tracking-wide text-warning">Editar dados nesta proposta</p>
                  <IconButton label="Fechar" tone="neutro" onClick={() => setMostrarOverride(false)}><IconX className="w-4 h-4" /></IconButton>
                </div>
                <p className="text-xs text-slate-500">Estes dados valem só para esta proposta e não alteram o cadastro do cliente. Campos em branco usam os dados do cadastro.</p>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <Input id="ov-nome" label="Razão social / Nome" value={overrideDraft.nome ?? ''} onChange={(e) => definirOverride('nome', e.target.value)} className="sm:col-span-2" />
                  <Input id="ov-documento" label="CNPJ / Documento" value={overrideDraft.documento ?? ''} onChange={(e) => definirOverride('documento', e.target.value)} />
                  <Input id="ov-telefone" label="Telefone" value={overrideDraft.telefone ?? ''} onChange={(e) => definirOverride('telefone', e.target.value)} />
                  <Input id="ov-endereco" label="Endereço" value={overrideDraft.endereco ?? ''} onChange={(e) => definirOverride('endereco', e.target.value)} className="sm:col-span-2" />
                  <Input id="ov-municipio" label="Município" value={overrideDraft.municipio ?? ''} onChange={(e) => definirOverride('municipio', e.target.value)} />
                  <Select id="ov-estado" label="Estado (UF)" value={overrideDraft.estado ?? ''} onChange={(e) => definirOverride('estado', e.target.value)}>
                    <option value="">—</option>
                    {UFS.map((uf) => <option key={uf} value={uf}>{uf}</option>)}
                  </Select>
                  <Input id="ov-email" label="E-mail" value={overrideDraft.email ?? ''} onChange={(e) => definirOverride('email', e.target.value)} className="sm:col-span-2" />
                  <Input id="ov-contato" label="Contato (aos cuidados de)" value={overrideDraft.contato ?? ''} onChange={(e) => definirOverride('contato', e.target.value)} className="sm:col-span-2" />
                </div>
                <div className="flex items-center justify-between border-t border-warning/20 pt-3">
                  <Button type="button" variant="ghost" onClick={restaurarOverride}>Restaurar do cadastro</Button>
                  <div className="flex gap-2">
                    <Button type="button" variant="secondary" onClick={() => setMostrarOverride(false)}>Cancelar</Button>
                    <Button type="button" variant="primary" onClick={salvarOverride}>Aplicar</Button>
                  </div>
                </div>
              </div>
            )}

            <label className="flex items-center gap-2 text-sm text-slate-300 pt-1 cursor-pointer">
              <input
                type="checkbox"
                checked={!!form.endereco_entrega_diferente}
                onChange={(e) => setField('endereco_entrega_diferente', e.target.checked)}
                className="h-4 w-4 rounded border-border text-primary focus:ring-primary/50"
              />
              Endereço de entrega diferente do endereço de cobrança
            </label>
            {form.endereco_entrega_diferente && (
              // Simplificação: sem busca de CEP (ver relatório da task) — texto livre.
              <Input
                id="endereco-entrega-texto"
                label="Endereço de entrega"
                value={enderecoEntregaTexto}
                onChange={(e) => setField('endereco_entrega', { texto: e.target.value })}
                placeholder="Endereço completo de entrega"
              />
            )}
          </Secao>

          {/* ── Aparelhos ── */}
          {form.cliente != null && (
            <Secao titulo="Aparelhos" icon={<IconFrota className="w-3.5 h-3.5" />}>
              {carregandoFrota ? (
                <div className="flex justify-center py-6"><Spinner className="w-6 h-6" /></div>
              ) : !frota || frota.length === 0 ? (
                <p className="text-sm text-slate-500">Nenhum aparelho cadastrado para este cliente.</p>
              ) : (
                <>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none"><IconSearch className="w-4 h-4" /></span>
                    <input
                      value={buscaAparelho}
                      onChange={(e) => setBuscaAparelho(e.target.value)}
                      placeholder="Buscar aparelho por descrição ou série"
                      className={`pl-9 ${inputClass}`}
                    />
                  </div>
                  {(() => {
                    const q = buscaAparelho.trim().toLowerCase()
                    const frotaFiltrada = q
                      ? frota.filter((a) => (a.equipamento_descricao ?? '').toLowerCase().includes(q) || (a.serie ?? '').toLowerCase().includes(q))
                      : frota
                    if (frotaFiltrada.length === 0) {
                      return <p className="mt-2 text-sm text-slate-500">Nenhum aparelho encontrado para “{buscaAparelho}”.</p>
                    }
                    return (
                      <ul className="mt-2 max-h-96 space-y-2 overflow-y-auto pr-1">
                        {frotaFiltrada.map((a) => {
                          const s = STATUS_CALIBRACAO[a.status_calibracao as StatusCalibracao] ?? STATUS_CALIBRACAO.sem_data
                          return (
                            <li key={a.id} className="flex items-center justify-between gap-3 rounded-lg border border-border bg-background-elevated px-3 py-2.5">
                              <label className="flex items-center gap-3 min-w-0 cursor-pointer">
                                <input
                                  type="checkbox"
                                  aria-label={a.equipamento_descricao ?? `Aparelho #${a.id}`}
                                  checked={aparelhosSelecionados.includes(a.id)}
                                  onChange={() => toggleAparelho(a.id)}
                                  className="h-4 w-4 rounded border-border text-primary focus:ring-primary/50 shrink-0"
                                />
                                <span className="min-w-0">
                                  <span className="block truncate font-medium text-slate-200">{a.equipamento_descricao ?? '—'}</span>
                                  <span className="block text-xs text-slate-500">{a.serie || a.patrimonio || '—'}</span>
                                  <span className="block text-xs text-slate-400">{descreverVencimento(a.prox_calibragem)}</span>
                                </span>
                              </label>
                              <Badge tone={s.tone}>{s.label}</Badge>
                            </li>
                          )
                        })}
                      </ul>
                    )
                  })()}
                </>
              )}
            </Secao>
          )}

          {/* ── Identificação ── */}
          <Secao titulo="Identificação da Proposta">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Nº Proposta</label>
                <input readOnly value={editando && numero != null ? `#${numero}` : '(automático)'} className="w-full cursor-default rounded-lg border border-border bg-background-elevated/50 px-3 py-2.5 text-sm text-slate-500" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Vendedor</label>
                <input readOnly value={form.vendedor || '(automático)'} className="w-full cursor-default rounded-lg border border-border bg-background-elevated/50 px-3 py-2.5 text-sm text-slate-500" />
              </div>
              <Input id="data-proposta" label="Data da Proposta" type="date" value={form.data ?? ''} onChange={(e) => setField('data', e.target.value)} />
            </div>
          </Secao>

          {/* ── Itens ── */}
          <Secao titulo="Itens de Produto ou Serviço" icon={<IconTag className="w-3.5 h-3.5" />}>
            {itens.length === 0 ? (
              <p className="mb-3 text-sm text-slate-500">Nenhum item adicionado.</p>
            ) : (
              <div data-testid="tabela-itens" className="mb-3 overflow-x-auto rounded-lg border border-border">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border bg-background-elevated text-left">
                      <th className="px-2 py-2 font-medium text-slate-400">Descrição</th>
                      <th className="w-20 px-2 py-2 font-medium text-slate-400">SKU</th>
                      <th className="w-16 px-2 py-2 font-medium text-slate-400">Qtde</th>
                      <th className="w-16 px-2 py-2 font-medium text-slate-400">UN</th>
                      <th className="w-24 px-2 py-2 font-medium text-slate-400">Preço un.</th>
                      <th className="w-24 px-2 py-2 font-medium text-slate-400">Total</th>
                      <th className="w-8 px-2 py-2" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {itens.map((item, idx) => {
                      const totalLinha = (Number(item.quantidade) || 0) * (Number(item.preco_un) || 0)
                      return (
                        <tr key={idx}>
                          <td className="px-2 py-2 relative">
                            <input
                              ref={(el) => { descricaoRefs.current[idx] = el }}
                              type="text"
                              value={item.descricao}
                              onChange={(e) => { atualizarItem(idx, 'descricao', e.target.value); abrirBuscaCatalogo(idx) }}
                              onFocus={() => abrirBuscaCatalogo(idx)}
                              placeholder="Digite para buscar no catálogo…"
                              className="w-full rounded border border-border bg-background-elevated px-2 py-1.5 text-sm text-slate-100"
                            />
                          </td>
                          <td className="px-2 py-2">
                            <input type="text" value={item.sku ?? ''} onChange={(e) => atualizarItem(idx, 'sku', e.target.value)} className="w-full rounded border border-border bg-background-elevated px-2 py-1.5 text-sm text-slate-100" />
                          </td>
                          <td className="px-2 py-2">
                            <input type="number" min={0} value={item.quantidade ?? 1} onChange={(e) => atualizarItem(idx, 'quantidade', Number(e.target.value))} className="w-full rounded border border-border bg-background-elevated px-2 py-1.5 text-sm text-slate-100" />
                          </td>
                          <td className="px-2 py-2">
                            <input type="text" value={item.unidade ?? ''} onChange={(e) => atualizarItem(idx, 'unidade', e.target.value)} className="w-full rounded border border-border bg-background-elevated px-2 py-1.5 text-sm text-slate-100" />
                          </td>
                          <td className="px-2 py-2">
                            <input type="number" min={0} step="0.01" value={item.preco_un ?? 0} onChange={(e) => atualizarItem(idx, 'preco_un', Number(e.target.value))} className="w-full rounded border border-border bg-background-elevated px-2 py-1.5 text-sm text-slate-100" />
                          </td>
                          <td className="px-2 py-2 text-slate-300">R$ {formatarMoeda(totalLinha)}</td>
                          <td className="px-2 py-2">
                            <IconButton label="Remover item" tone="excluir" onClick={() => removerItem(idx)}><IconTrash className="w-3.5 h-3.5" /></IconButton>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
            <Button type="button" variant="ghost" onClick={adicionarItem}><IconPlus className="w-3.5 h-3.5" /> Adicionar item</Button>
            {linhaAberta !== null && posDropdown && createPortal(
              <div
                ref={dropdownRef}
                style={{ position: 'fixed', top: posDropdown.top, left: posDropdown.left, width: Math.max(posDropdown.width, 352) }}
                className="z-50 max-h-80 overflow-y-auto rounded-lg border border-border bg-background-surface shadow-xl"
              >
                {resultadosParaLinha(linhaAberta).length === 0 ? (
                  <p className="px-3 py-2.5 text-sm text-slate-500">
                    {(itens[linhaAberta]?.descricao ?? '').trim() ? 'Nenhum resultado no catálogo' : 'Digite para buscar no catálogo'}
                  </p>
                ) : (
                  <ul className="divide-y divide-border">
                    {resultadosParaLinha(linhaAberta).map((r, i) => (
                      <li key={i}>
                        <button
                          type="button"
                          onClick={() => selecionarItemCatalogo(linhaAberta, r)}
                          className="block w-full px-3 py-2.5 text-left text-sm hover:bg-background-elevated"
                        >
                          <span className="block font-medium text-slate-200">{r.nome}</span>
                          <span className="block text-xs text-slate-500">{r.sku ? `SKU ${r.sku} · ` : ''}R$ {formatarMoeda(r.preco)}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>,
              document.body,
            )}
          </Secao>

          {/* ── Outros itens ou serviços (bloco técnico) ── */}
          <Secao titulo="Outros Itens ou Serviços" icon={<IconNote className="w-3.5 h-3.5" />}>
            <div className="mb-2 flex flex-wrap items-end gap-2">
              <div className="w-56">
                <Select id="modelo-texto-proposta" label="Modelo do texto" value={modeloTexto} onChange={(e) => setModeloTexto(e.target.value as 'demais' | 'phoebus')}>
                  <option value="demais">Demais aparelhos</option>
                  <option value="phoebus">Aparelho Phoebus</option>
                </Select>
              </div>
              <Button type="button" variant="secondary" onClick={aplicarModeloTexto}>Aplicar modelo</Button>
              <span className="text-[11px] text-slate-500">Usa os aparelhos marcados acima; substitui o texto abaixo.</span>
            </div>
            <RichText
              key={editorKey}
              value={form.outros_itens ?? ''}
              onChange={(v) => setField('outros_itens', v)}
              placeholder="Descreva outros itens, serviços ou condições especiais…"
            />
          </Secao>

          {/* ── Totais ── */}
          <Secao titulo="Totais">
            <div className="flex items-center justify-between rounded-lg bg-background-elevated px-4 py-3">
              <span className="text-sm text-slate-400">Total dos itens</span>
              <span data-testid="total-itens" className="font-medium text-slate-100">R$ {formatarMoeda(totalItens)}</span>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Input
                id="desconto-proposta"
                label="Desconto (R$)"
                inputMode="decimal"
                placeholder="0,00"
                value={descontoStr}
                onChange={(e) => {
                  const s = sanitizarDecimal(e.target.value)
                  setDescontoStr(s)
                  setField('desconto', converterDecimal(s))
                }}
              />
              <Input
                id="frete-proposta"
                label="Frete (R$)"
                inputMode="decimal"
                placeholder="0,00"
                value={freteStr}
                onChange={(e) => {
                  const s = sanitizarDecimal(e.target.value)
                  setFreteStr(s)
                  setField('frete', converterDecimal(s))
                }}
              />
            </div>
            <div className="flex items-center justify-between rounded-lg border border-primary/30 bg-primary/10 px-4 py-3">
              <span className="font-semibold text-slate-100">Total da Proposta</span>
              <span data-testid="total-proposta" className="text-xl font-bold text-primary">R$ {formatarMoeda(totalProposta)}</span>
            </div>
          </Secao>

          {/* ── Transportador ── */}
          <Secao titulo="Transportador">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Input id="forma-envio-proposta" label="Forma de envio" value={form.forma_envio ?? ''} onChange={(e) => setField('forma_envio', e.target.value)} placeholder="Ex: Sedex, PAC, Transportadora…" />
              <Input id="forma-frete-proposta" label="Forma de frete" value={form.forma_frete ?? ''} onChange={(e) => setField('forma_frete', e.target.value)} placeholder="Ex: CIF, FOB…" />
              <Input id="transportador-proposta" label="Nome do transportador" value={form.transportador ?? ''} onChange={(e) => setField('transportador', e.target.value)} placeholder="Nome da transportadora" />
            </div>
          </Secao>

          {/* ── Condições comerciais ── */}
          <Secao titulo="Condições Comerciais">
            <Input
              id="condicao-pagamento-proposta"
              label="Condição de pagamento / Parcelas"
              value={form.condicao_pagamento ?? ''}
              onChange={(e) => setField('condicao_pagamento', e.target.value)}
              placeholder="Ex: 30/60/90 dias, à vista, boleto…"
            />
          </Secao>

          {/* ── Condições gerais ── */}
          <Secao titulo="Condições Gerais">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Input
                id="validade-dias-proposta"
                label="Validade (dias)"
                type="number"
                min={0}
                max={3650}
                value={form.validade_dias ?? ''}
                onChange={(e) => setField('validade_dias', e.target.value ? Math.max(0, Math.floor(Number(e.target.value))) : null)}
                placeholder="Ex: 30"
              />
              <Input id="data-entrega-proposta" label="Data prevista de entrega" type="date" value={form.data_entrega ?? ''} onChange={(e) => setField('data_entrega', e.target.value)} />
              <Input
                id="descricao-entrega-proposta"
                label="Descrição do prazo"
                value={form.descricao_entrega ?? ''}
                onChange={(e) => setField('descricao_entrega', e.target.value)}
                placeholder="Ex: 15 dias úteis após aprovação"
              />
            </div>
          </Secao>

          {/* ── Observações e assinatura ── */}
          <Secao titulo="Observações e Assinatura">
            <div>
              <label htmlFor="observacoes-proposta" className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Observações</label>
              <textarea
                id="observacoes-proposta"
                value={form.observacoes ?? ''}
                onChange={(e) => setField('observacoes', e.target.value)}
                rows={3}
                placeholder="Observações adicionais sobre a proposta…"
                className={`${inputClass} resize-none`}
              />
            </div>
            <div>
              <label htmlFor="assinatura-proposta" className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Assinatura / Responsável</label>
              <textarea
                id="assinatura-proposta"
                value={form.assinatura ?? ''}
                onChange={(e) => setField('assinatura', e.target.value)}
                rows={2}
                placeholder={'Atenciosamente,\nNome do responsável'}
                className={`${inputClass} resize-none`}
              />
            </div>
          </Secao>

          {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
        </form>
      )}
    </Modal>
  )
}
