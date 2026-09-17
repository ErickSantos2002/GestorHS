import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { IconButton } from '../../components/ui/IconButton'
import { IconSearch, IconPlus, IconTrash, IconClientes, IconFrota, IconTag, IconNote } from '../../components/ui/icons'
import { RichText } from '../../components/ui/RichText'
import { useAuth } from '../../auth/AuthContext'
import { ApiError } from '../../lib/api'
import { hojeISO } from '../../lib/datas'
import { soDigitos } from '../../lib/documento'
import { cn } from '../../lib/utils'
import { formatarMoeda } from '../../lib/moeda'
import { descreverVencimento } from './aparelhosFrota'
import { clientesApi, type Cliente } from '../clientes/api'
import { empresasApi, destinatariosApi, type DestinatarioResultado, type Empresa } from '../empresas/api'
import {
  dadosDeCliente, dadosDeEmpresa, dadosVazios, sugestoesDeCliente, sugestoesDeEmpresa,
  type DadosEmpresa,
} from '../empresas/dadosEmpresa'
import { DadosEmpresaForm } from '../empresas/DadosEmpresaForm'
import { MatrizSelect } from '../empresas/MatrizSelect'
import { STATUS_CALIBRACAO, type StatusCalibracao } from '../frota/api'
import {
  propostasApi, frotaDoCliente, servicosApi, produtosApi,
  type PropostaCreate, type PropostaItemCreate, type EquipamentoClienteFrota,
} from './api'
import { buildDefaultOtherItems, buildPhoebusOtherItems, DEFAULT_NOTES } from './propostaDefaults'
import { DestinatarioBusca } from './DestinatarioBusca'
import { clienteDaFrota, descreverSelecao, montarDestinatario, type Selecao } from './destinatario'
import { camposObrigatoriosFaltando, htmlTemTexto, obrigatoriosDaProposta, ROTULO_CONTATO, validarProposta } from './validacao'

const sanitizarDecimal = (v: string) => v.replace(/[^0-9,]/g, '').replace(/(,.*),/g, '$1')
const converterDecimal = (v: string) => parseFloat(v.replace(',', '.')) || 0
const numeroParaTexto = (n?: number | null) => (n ? String(n).replace('.', ',') : '')

const ITEM_VAZIO = (): PropostaItemCreate => ({ descricao: '', sku: '', quantidade: 1, unidade: 'Unid', preco_un: 0 })

const EMPTY_FORM = (): PropostaCreate => ({
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
  observacoes: '',
  assinatura: '',
  itens: [],
  aparelhos: [],
})

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

export function PropostaModal({ propostaId, duplicarDe, onClose, onSalvo }: {
  propostaId?: number | null
  /** Id da proposta-modelo: abre como proposta NOVA pré-preenchida, sem salvar nada até confirmar. */
  duplicarDe?: number | null
  onClose: () => void
  onSalvo?: (id: number) => void
}) {
  const { user } = useAuth()
  const editando = propostaId != null
  const duplicando = !editando && duplicarDe != null

  const [form, setForm] = useState<PropostaCreate>(EMPTY_FORM())
  const [itens, setItens] = useState<PropostaItemCreate[]>([])
  const [descontoStr, setDescontoStr] = useState('')
  const [freteStr, setFreteStr] = useState('')
  const [numero, setNumero] = useState<number | null>(null)
  const [editorKey, setEditorKey] = useState(0)
  const [modeloTexto, setModeloTexto] = useState<'demais' | 'phoebus'>('demais')

  const [carregando, setCarregando] = useState(editando || duplicarDe != null)
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState('')

  // ─── Destinatario ─────────────────────────────────────────────────────
  // Os dados editados aqui ATUALIZAM o cadastro de origem (Cliente/Empresa) ao
  // salvar — nao existe mais "dados so nesta proposta". A proposta guarda uma
  // copia congelada, montada pelo servidor.
  const [selecao, setSelecao] = useState<Selecao | null>(null)
  const [dados, setDados] = useState<DadosEmpresa>(dadosVazios())
  const [carregandoDestinatario, setCarregandoDestinatario] = useState(false)
  /** Ultimo Cliente escolhido: vira a matriz sugerida de uma empresa nova. */
  const [ultimoCliente, setUltimoCliente] = useState<Cliente | null>(null)
  /** Cadastro existente com o documento recusado (409) — oferece "Usar este cadastro". */
  const [conflito, setConflito] = useState<DestinatarioResultado | null>(null)
  // Marca em vermelho os obrigatorios em branco, mas so depois da primeira
  // tentativa de salvar: campo vazio ainda nao visitado nao e' erro.
  const [tentouSalvar, setTentouSalvar] = useState(false)
  const frotaClienteId = clienteDaFrota(selecao)
  const frotaAnteriorRef = useRef<number | null | undefined>(undefined)

  // ─── Frota / Aparelhos ────────────────────────────────────────────────
  const [frota, setFrota] = useState<EquipamentoClienteFrota[] | null>(null)
  const [carregandoFrota, setCarregandoFrota] = useState(false)
  /** A busca da frota falhou — diferente de frota vazia (ver o efeito da frota). */
  const [erroFrota, setErroFrota] = useState(false)
  const [aparelhosSelecionados, setAparelhosSelecionados] = useState<number[]>([])
  const [buscaAparelho, setBuscaAparelho] = useState('')
  /** Aparelhos salvos que nao estao mais na frota e foram retirados ao abrir. */
  const [aparelhosRetirados, setAparelhosRetirados] = useState(0)

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

  // ─── Destinatario de proposta ja salva (edicao/duplicacao) ────────────
  // Abre com o cadastro ATUAL, nao com a copia congelada: salvar refaz a copia.
  // Aparelho salvo sem frota para conferir (sem destinatario, empresa sem
  // matriz) sairia invisivel no payload e o servidor recusaria (422).
  async function carregarDestinatario(p: {
    empresa: number | null; cliente: number | null; aparelhos: { equipamento_cliente: number | null }[]
  }) {
    const salvos = p.aparelhos.filter((a) => a.equipamento_cliente != null).length
    const retirarTodos = () => {
      setAparelhosSelecionados([])
      setAparelhosRetirados(salvos)
    }
    if (p.empresa == null && p.cliente == null) {
      retirarTodos()
      return
    }
    setCarregandoDestinatario(true)
    try {
      if (p.empresa != null) {
        const empresa = await empresasApi.obter(p.empresa)
        setSelecao({ tipo: 'empresa', empresa })
        setDados(dadosDeEmpresa(empresa))
        if (empresa.cliente == null) retirarTodos()
      } else if (p.cliente != null) {
        const cliente = await clientesApi.obter(p.cliente)
        setSelecao({ tipo: 'cliente', cliente })
        setUltimoCliente(cliente)
        setDados(dadosDeCliente(cliente))
      }
    } catch {
      setAparelhosSelecionados([])
      setErro('Falha ao carregar os dados do destinatário')
    } finally {
      setCarregandoDestinatario(false)
    }
  }

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
        void carregarDestinatario(p)
      })
      .catch(() => { if (vivo) setErro('Falha ao carregar a proposta') })
      .finally(() => { if (vivo) setCarregando(false) })
    return () => { vivo = false }
  }, [propostaId])

  // ─── Semente de duplicação: nova proposta pré-preenchida ──────────────
  // Copia o conteúdo da proposta original, mas com a identidade de quem está
  // duplicando (vendedor + assinatura) e data de hoje. Nada é salvo até a
  // pessoa confirmar em "Criar Proposta"; cancelar não deixa rastro. Número
  // fica automático (null) e o histórico/versões não são copiados.
  useEffect(() => {
    if (propostaId || !duplicarDe) return
    let vivo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCarregando(true)
    propostasApi.obter(duplicarDe)
      .then((p) => {
        if (!vivo) return
        setForm({
          contato: p.contato ?? '',
          vendedor: user?.nome ?? '',
          data: hojeISO(),
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
          observacoes: p.observacoes ?? '',
          assinatura: `Atenciosamente,\n${user?.nome ?? ''}`,
          itens: [],
          aparelhos: [],
        })
        setItens(p.itens.map((i) => ({ descricao: i.descricao, sku: i.sku, quantidade: i.quantidade, unidade: i.unidade, preco_un: i.preco_un })))
        setAparelhosSelecionados(p.aparelhos.map((a) => a.equipamento_cliente).filter((x): x is number => x != null))
        setDescontoStr(numeroParaTexto(p.desconto))
        setFreteStr(numeroParaTexto(p.frete))
        setEditorKey((k) => k + 1)
        void carregarDestinatario(p)
      })
      .catch(() => { if (vivo) setErro('Falha ao carregar a proposta para duplicar') })
      .finally(() => { if (vivo) setCarregando(false) })
    return () => { vivo = false }
  }, [propostaId, duplicarDe, user])

  // ─── Defaults de proposta nova ────────────────────────────────────────
  useEffect(() => {
    if (propostaId || duplicarDe) return
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

  // ─── Frota do cliente matriz ──────────────────────────────────────────
  // Muda com o destinatario: Cliente -> a propria frota; Empresa -> a da matriz.
  // Na primeira carga (edicao) os aparelhos salvos sao mantidos; numa troca de
  // verdade eles sao limpos, porque eram de outra frota.
  useEffect(() => {
    const anterior = frotaAnteriorRef.current
    frotaAnteriorRef.current = frotaClienteId
    if (anterior !== undefined && anterior !== null && anterior !== frotaClienteId) {
      setAparelhosSelecionados([])
      setBuscaAparelho('')
    }
    if (frotaClienteId == null) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setFrota(null)
      return
    }
    let vivo = true
    setCarregandoFrota(true)
    setErroFrota(false)
    frotaDoCliente(frotaClienteId)
      .then((itensFrota) => { if (vivo) { setFrota(itensFrota); setCarregandoFrota(false) } })
      // Frota que NAO carregou nao e' frota vazia: deixar `frota` nula mantem os
      // aparelhos marcados de fora da conferencia abaixo — senao uma queda de rede
      // apagaria em silencio os aparelhos que a proposta ja tinha.
      .catch(() => { if (vivo) { setFrota(null); setErroFrota(true); setCarregandoFrota(false) } })
    return () => { vivo = false }
  }, [frotaClienteId])

  // ─── Aparelhos salvos que sairam da frota ─────────────────────────────
  // Transferido, matriz trocada: o aparelho continuaria marcado sem aparecer
  // na lista e o servidor recusaria salvar. Roda so quando a frota chega —
  // numa troca de destinatario a selecao ja foi limpa antes.
  useEffect(() => {
    if (!frota) return
    const ids = new Set(frota.map((a) => a.id))
    const fora = aparelhosSelecionados.filter((id) => !ids.has(id))
    if (fora.length === 0) return
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setAparelhosSelecionados((cur) => cur.filter((id) => ids.has(id)))
    setAparelhosRetirados(fora.length)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [frota])

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

  // ─── Destinatario handlers ────────────────────────────────────────────
  async function escolherDestinatario(r: DestinatarioResultado, manterContato?: { email: string; telefone: string }) {
    setConflito(null)
    setErro('')
    setAparelhosRetirados(0)
    setTentouSalvar(false)
    setCarregandoDestinatario(true)
    try {
      if (r.tipo === 'cliente') {
        const cliente = await clientesApi.obter(r.id)
        setSelecao({ tipo: 'cliente', cliente })
        setUltimoCliente(cliente)
        setDados({ ...dadosDeCliente(cliente), ...manterContato })
      } else {
        const empresa: Empresa = await empresasApi.obter(r.id)
        setSelecao({ tipo: 'empresa', empresa })
        setDados({ ...dadosDeEmpresa(empresa), ...manterContato })
      }
    } catch {
      setErro('Falha ao carregar os dados do destinatário')
    } finally {
      setCarregandoDestinatario(false)
    }
  }

  function cadastrarEmpresa(documento: string) {
    setConflito(null)
    setErro('')
    setAparelhosRetirados(0)
    setTentouSalvar(false)
    setSelecao({ tipo: 'nova_empresa', matriz: ultimoCliente ? { id: ultimoCliente.id, nome: ultimoCliente.nome } : null })
    setDados(dadosVazios(documento))
  }

  function trocarDestinatario() {
    setSelecao(null)
    setDados(dadosVazios())
    setConflito(null)
    setErro('')
    setAparelhosRetirados(0)
    setTentouSalvar(false)
  }

  const sugestoes = selecao?.tipo === 'cliente'
    ? sugestoesDeCliente(selecao.cliente)
    : selecao?.tipo === 'empresa' ? sugestoesDeEmpresa(selecao.empresa) : undefined
  const nomeDoCadastro = selecao?.tipo === 'cliente'
    ? selecao.cliente.nome
    : selecao?.tipo === 'empresa' ? selecao.empresa.nome : null
  const exigirDocumento = selecao?.tipo === 'nova_empresa'
  const faltandoContato = tentouSalvar && camposObrigatoriosFaltando(dados, form.contato ?? '', exigirDocumento).includes(ROTULO_CONTATO)

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
  // Enter num campo de uma linha NAO submete: o formulario tem varios inputs
  // de busca (cliente, aparelho, descricao do item) e o submit implicito do
  // browser criava proposta em branco. Textarea e o editor rico ficam livres.
  function aoTeclarNoForm(e: ReactKeyboardEvent<HTMLFormElement>) {
    if (e.key !== 'Enter') return
    if ((e.target as HTMLElement).tagName === 'INPUT') e.preventDefault()
  }

  async function submeter(e: FormEvent) {
    e.preventDefault()
    const problema = validarProposta({
      selecao,
      dados,
      contato: form.contato ?? '',
      outrosItens: form.outros_itens,
      carregando: carregandoDestinatario,
    })
    if (problema) {
      setTentouSalvar(true)
      setErro(problema)
      return
    }
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
        destinatario: selecao ? montarDestinatario(selecao, dados) : null,
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
      // Documento de empresa nova ja existe: acha o cadastro para oferecer usa-lo.
      if (err instanceof ApiError && err.status === 409 && selecao?.tipo === 'nova_empresa') {
        const doc = soDigitos(dados.documento)
        const achados = await destinatariosApi.buscar(doc).catch(() => [])
        setConflito(achados.find((r) => soDigitos(r.documento) === doc) ?? null)
      }
    } finally {
      setSalvando(false)
    }
  }

  const enderecoEntregaTexto = (form.endereco_entrega as { texto?: string } | null)?.texto ?? ''

  return (
    <Modal
      open
      onClose={onClose}
      title={editando ? `Editar Proposta${numero != null ? ` #${numero}` : ''}` : duplicando ? 'Duplicar Proposta' : 'Nova Proposta'}
      size="5xl"
      // Formulario longo: clique fora nao fecha — so o X ou Cancelar.
      closeOnBackdrop={false}
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
        <form id="form-proposta" onSubmit={submeter} onKeyDown={aoTeclarNoForm} className="space-y-6">

          {/* ── Destinatário ── */}
          <Secao titulo="Destinatário" icon={<IconClientes className="w-3.5 h-3.5" />} primeira>
            {selecao == null ? (
              <DestinatarioBusca onEscolher={(r) => void escolherDestinatario(r)} onCadastrarEmpresa={cadastrarEmpresa} />
            ) : (
              <div className="space-y-3 rounded-lg border border-border bg-background-elevated/40 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate font-semibold text-slate-100">{nomeDoCadastro ?? (dados.nome || 'Nova empresa')}</p>
                    <Badge tone={selecao.tipo === 'cliente' ? 'primary' : 'info'}>{descreverSelecao(selecao)}</Badge>
                  </div>
                  <Button type="button" variant="ghost" onClick={trocarDestinatario}>Trocar destinatário</Button>
                </div>
                <p className="text-xs text-slate-500">
                  {selecao.tipo === 'nova_empresa'
                    ? `Ao salvar a proposta, a empresa ${dados.nome || 'nova'} é cadastrada com estes dados.`
                    : `Alterações nestes dados atualizam o cadastro de ${nomeDoCadastro ?? ''}.`}
                  {' '}E-mail, telefone e contato são sempre conferidos a cada proposta.
                </p>
                {carregandoDestinatario ? (
                  <div className="flex justify-center py-6"><Spinner className="w-6 h-6" /></div>
                ) : (
                  <DadosEmpresaForm
                    dados={dados}
                    onChange={setDados}
                    documentoTravado={selecao.tipo !== 'nova_empresa'}
                    sugestoes={sugestoes}
                    obrigatorios={obrigatoriosDaProposta(exigirDocumento)}
                    destacarFaltando={tentouSalvar}
                    idPrefixo="dest"
                  >
                    {selecao.tipo === 'nova_empresa' && (
                      <MatrizSelect valor={selecao.matriz} onChange={(matriz) => setSelecao({ tipo: 'nova_empresa', matriz })} />
                    )}
                    {/* A matriz tambem e' editavel numa Empresa ja cadastrada: e' de
                        onde vem a frota, e filial sem matriz nao aceita aparelho. Trocar
                        aqui recarrega a frota (clienteDaFrota) e grava no cadastro. */}
                    {selecao.tipo === 'empresa' && (
                      <MatrizSelect
                        valor={selecao.empresa.cliente != null
                          ? { id: selecao.empresa.cliente, nome: selecao.empresa.matriz_nome }
                          : null}
                        onChange={(matriz) => setSelecao({
                          tipo: 'empresa',
                          empresa: { ...selecao.empresa, cliente: matriz?.id ?? null, matriz_nome: matriz?.nome ?? null },
                        })}
                      />
                    )}
                    {/* "Aos cuidados de" e' coluna da PROPOSTA, nao do cadastro. */}
                    <div className="sm:col-span-2">
                      <Input
                        id="dest-contato"
                        label={`${ROTULO_CONTATO} *`}
                        value={form.contato ?? ''}
                        onChange={(e) => setField('contato', e.target.value)}
                        className={cn(faltandoContato && 'border-danger')}
                        placeholder="Nome do contato no cliente"
                      />
                    </div>
                  </DadosEmpresaForm>
                )}
                {conflito && (
                  <div className="flex flex-wrap items-center gap-3 rounded-lg border border-warning/40 bg-warning/5 px-3 py-2 text-xs">
                    <span className="text-slate-300">
                      Este documento já é {conflito.tipo === 'cliente' ? 'do cliente' : 'da empresa'} <strong>{conflito.nome}</strong>.
                    </span>
                    <Button type="button" variant="secondary"
                      onClick={() => void escolherDestinatario(conflito, { email: dados.email, telefone: dados.telefone })}>
                      Usar este cadastro
                    </Button>
                  </div>
                )}
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

          {/* ── Introdução ── */}
          <Secao titulo="Introdução">
            <div>
              <label htmlFor="intro-proposta" className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Introdução</label>
              <textarea
                id="intro-proposta"
                value={form.intro ?? ''}
                onChange={(e) => setField('intro', e.target.value)}
                rows={3}
                placeholder="Texto de introdução da proposta (opcional)"
                className={`${inputClass} resize-none`}
              />
            </div>
          </Secao>

          {/* ── Aparelhos ── */}
          {aparelhosRetirados > 0 && (
            <p className="text-sm font-medium text-warning">
              {aparelhosRetirados} aparelho(s) não estão mais na frota e foram retirados da proposta.
            </p>
          )}
          {frotaClienteId != null && (
            <Secao titulo="Aparelhos" icon={<IconFrota className="w-3.5 h-3.5" />}>
              {carregandoFrota ? (
                <div className="flex justify-center py-6"><Spinner className="w-6 h-6" /></div>
              ) : erroFrota ? (
                <p className="text-sm font-medium text-danger">
                  Não foi possível carregar a frota. Os aparelhos já marcados na proposta continuam valendo.
                </p>
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
          <Secao titulo="Outros Itens ou Serviços (obrigatório)" icon={<IconNote className="w-3.5 h-3.5" />}>
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
            {!htmlTemTexto(form.outros_itens) && (
              <p className="text-xs font-medium text-danger">
                Aplique o modelo (ou escreva o conteúdo) — este bloco vai em toda proposta.
              </p>
            )}
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
