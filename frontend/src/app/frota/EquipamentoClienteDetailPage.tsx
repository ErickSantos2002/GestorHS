import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { Table, TH, TD } from '../../components/ui/Table'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { isAdmin, podeAbrirOS } from '../../auth/roles'
import { AbrirOSModal } from '../ordens/AbrirOSModal'
import { TransferirModal } from './TransferirModal'
import { ordensApi, formatData, osAtiva, TIPO_SERVICO, type OrdemListItem } from '../ordens/api'
import { equipamentosClienteApi, STATUS_CALIBRACAO, type EquipamentoCliente, type EquipamentoClientePayload, type Historico, type StatusCalibracao, type EquipCertItem, type Transferencia } from './api'
import { equipamentosApi, type Equipamento } from '../cadastros/api'
import { PageContainer, DetailGrid, DetailMain, DetailAside } from '../../components/ui/Page'

const VAZIO: EquipamentoClientePayload = {
  cliente: 0, equipamento: 0, modulo: 0, serie: null, patrimonio: null,
  datacompra: null, ult_calibragem: null, prox_calibragem: null, ativo: true, status: 'A',
}

function Secao({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <div className="rounded-2xl bg-background-surface border border-border p-5 space-y-4">
      <h2 className="text-sm font-semibold text-slate-100">{titulo}</h2>
      {children}
    </div>
  )
}

export function EquipamentoClienteDetailPage() {
  const { id } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const editando = id !== undefined
  const podeEditar = isAdmin(user)
  const clienteParam = searchParams.get('cliente')
  const clienteId = clienteParam ? Number(clienteParam) : 0

  const [form, setForm] = useState<EquipamentoClientePayload>({ ...VAZIO, cliente: clienteId })
  const [obj, setObj] = useState<EquipamentoCliente | null>(null)
  const [catalogo, setCatalogo] = useState<Equipamento[]>([])
  const [historico, setHistorico] = useState<Historico[]>([])
  const [carregando, setCarregando] = useState(editando)
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [abrindoOS, setAbrindoOS] = useState(false)
  const [ordens, setOrdens] = useState<OrdemListItem[]>([])
  const [certs, setCerts] = useState<EquipCertItem[]>([])
  const [transferindo, setTransferindo] = useState(false)
  const [transferencias, setTransferencias] = useState<Transferencia[]>([])
  const [recarga, setRecarga] = useState(0)
  const [erroDownload, setErroDownload] = useState('')

  useEffect(() => {
    void equipamentosApi.listar().then(setCatalogo).catch(() => setCatalogo([]))
  }, [])

  useEffect(() => {
    if (!editando) return
    let ativo = true
    equipamentosClienteApi
      .obter(Number(id))
      .then((e) => {
        if (!ativo) return
        setObj(e)
        setForm({
          cliente: e.cliente, equipamento: e.equipamento, modulo: e.modulo, serie: e.serie, patrimonio: e.patrimonio,
          datacompra: e.datacompra, ult_calibragem: e.ult_calibragem, prox_calibragem: e.prox_calibragem,
          ativo: e.ativo, status: (e.status as 'A' | 'I' | 'M'),
        })
      })
      .catch((err) => {
        if (ativo) setErro(err instanceof ApiError ? err.message : 'Falha ao carregar')
      })
      .finally(() => {
        if (ativo) setCarregando(false)
      })
    void equipamentosClienteApi.historico(Number(id)).then((h) => { if (ativo) setHistorico(h) }).catch(() => {})
    void equipamentosClienteApi.ordens(Number(id)).then((o) => { if (ativo) setOrdens(o) }).catch(() => {})
    void equipamentosClienteApi.certificados(Number(id)).then((c) => { if (ativo) setCerts(c) }).catch(() => {})
    void equipamentosClienteApi.transferencias(Number(id)).then((t) => { if (ativo) setTransferencias(t) }).catch(() => {})
    return () => {
      ativo = false
    }
  }, [id, editando, recarga])

  function set<K extends keyof EquipamentoClientePayload>(chave: K, valor: EquipamentoClientePayload[K]) {
    setForm((f) => ({ ...f, [chave]: valor }))
  }

  async function salvar(e: FormEvent) {
    e.preventDefault(); setErro(''); setEnviando(true)
    try {
      if (editando) {
        const { cliente: _c, ...resto } = form
        void _c
        const atualizado = await equipamentosClienteApi.atualizar(Number(id), resto)
        setObj(atualizado)
      } else {
        const novo = await equipamentosClienteApi.criar(form)
        navigate(`/app/frota/${novo.id}`, { replace: true })
        return
      }
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao salvar')
    } finally {
      setEnviando(false)
    }
  }

  async function baixarPdf(os: number, tipo: 'C' | 'M') {
    setErroDownload('')
    try {
      await ordensApi.baixarCertificadoPdf(os, tipo)
    } catch {
      setErroDownload('Falha ao baixar PDF')
    }
  }

  async function excluir() {
    if (!editando) return
    if (!window.confirm('Excluir este aparelho?')) return
    setErro('')
    try {
      await equipamentosClienteApi.excluir(Number(id))
      navigate('/app/frota', { replace: true })
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao excluir')
    }
  }

  if (carregando) {
    return <div className="flex justify-center py-16"><Spinner className="w-8 h-8" /></div>
  }

  if (!editando && !clienteId) {
    return (
      <div className="px-4 md:px-6 py-6">
        <p className="text-sm text-slate-400">Abra a partir da frota de um cliente para cadastrar um aparelho.</p>
        <Button variant="secondary" className="mt-3" onClick={() => navigate('/app/frota')}>Ir para os Equipamentos</Button>
      </div>
    )
  }

  const ro = !podeEditar
  const statusCal: StatusCalibracao | null = obj ? obj.status_calibracao : null
  const sc = statusCal ? STATUS_CALIBRACAO[statusCal] : null
  const nomeCliente = obj?.cliente_nome ?? (clienteId ? `#${clienteId}` : '')
  const osEmAndamento = osAtiva(ordens)

  const formConteudo = (
    <>
      <Secao titulo="Aparelho">
        <Select id="ec-equipamento" label="Equipamento (catálogo)" value={form.equipamento ? String(form.equipamento) : ''} onChange={(e) => set('equipamento', Number(e.target.value))} disabled={ro} required>
          <option value="">— selecione —</option>
          {catalogo.map((c) => <option key={c.id} value={c.id}>{c.descricao}</option>)}
        </Select>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Input id="ec-serie" label="Série" value={form.serie ?? ''} onChange={(e) => set('serie', e.target.value || null)} disabled={ro} />
          <Input id="ec-patrimonio" label="Patrimônio" value={form.patrimonio ?? ''} onChange={(e) => set('patrimonio', e.target.value || null)} disabled={ro} />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Input id="ec-modulo" label="Módulo" type="number" value={String(form.modulo)} onChange={(e) => set('modulo', Number(e.target.value) || 0)} disabled={ro} />
          <Select id="ec-status" label="Situação" value={form.status} onChange={(e) => set('status', e.target.value as 'A' | 'I' | 'M')} disabled={ro}>
            <option value="A">Ativo</option>
            <option value="I">Inativo</option>
            <option value="M">Manutenção</option>
          </Select>
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input type="checkbox" checked={form.ativo} onChange={(e) => set('ativo', e.target.checked)} disabled={ro} className="accent-primary" />
          Ativo
        </label>
      </Secao>

      <Secao titulo="Calibração">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Input id="ec-datacompra" label="Compra" type="date" value={form.datacompra ?? ''} onChange={(e) => set('datacompra', e.target.value || null)} disabled={ro} />
          <Input id="ec-ult" label="Última calibração" type="date" value={form.ult_calibragem ?? ''} onChange={(e) => set('ult_calibragem', e.target.value || null)} disabled={ro} />
          <Input id="ec-prox" label="Próxima calibração" type="date" value={form.prox_calibragem ?? ''} onChange={(e) => set('prox_calibragem', e.target.value || null)} disabled={ro} />
        </div>
      </Secao>

      {podeEditar && (
        <button type="submit" disabled={enviando} className="w-full py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-60 transition-all">
          {editando ? 'Salvar alterações' : 'Criar aparelho'}
        </button>
      )}
    </>
  )

  return (
    <PageContainer>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-extrabold text-slate-100">{editando ? (obj?.equipamento_descricao || 'Aparelho') : 'Novo aparelho'}</h1>
          {sc && <Badge tone={sc.tone}>{sc.label}</Badge>}
        </div>
        <div className="flex gap-2">
          {editando && podeAbrirOS(user) && (
            osEmAndamento
              ? <Button onClick={() => navigate(`/app/ordens/${osEmAndamento.id}`)}>Ver OS #{osEmAndamento.id}</Button>
              : <Button onClick={() => setAbrindoOS(true)}>Abrir OS</Button>
          )}
          {editando && isAdmin(user) && (
            <Button
              variant="secondary"
              onClick={() => setTransferindo(true)}
              disabled={!!osEmAndamento}
              title={osEmAndamento ? 'Finalize a OS em andamento antes de transferir' : undefined}
            >
              Transferir
            </Button>
          )}
          {editando && podeEditar && <Button variant="danger" onClick={excluir}>Excluir</Button>}
          <Button variant="secondary" onClick={() => navigate('/app/frota')}>Voltar</Button>
        </div>
      </div>

      <p className="text-sm text-slate-400">
        Cliente:{' '}
        {obj?.cliente
          ? <Link to={`/app/clientes/${obj.cliente}`} className="text-primary hover:underline">{nomeCliente}</Link>
          : <span>{nomeCliente}</span>}
      </p>
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}

      {editando ? (
        <DetailGrid>
          <DetailMain>
            <form className="space-y-6" onSubmit={salvar}>{formConteudo}</form>
          </DetailMain>
          <DetailAside>
            {obj && (obj.calib_cert || obj.calib_situacao || obj.calib_teste_media) && (
              <Secao titulo="Última calibração (resultado da OS)">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm text-slate-300">
                  <p>Certificado: <span className="text-slate-100">{obj.calib_cert ?? '—'}</span></p>
                  <p>Situação: <span className="text-slate-100">{obj.calib_situacao ?? '—'}</span></p>
                  <p>Temperatura: <span className="text-slate-100">{obj.calib_temp ?? '—'}</span></p>
                  <p>Pressão: <span className="text-slate-100">{obj.calib_pressao ?? '—'}</span></p>
                  <p>Média dos testes: <span className="text-slate-100">{obj.calib_teste_media ?? '—'}</span></p>
                </div>
              </Secao>
            )}
            <Secao titulo="Histórico de movimentação">
              {historico.length === 0 ? (
                <p className="text-sm text-slate-500">Sem movimentações.</p>
              ) : (
                <Table head={<><TH>Data</TH><TH>Saída</TH><TH>Entrada</TH></>}>
                  {historico.map((m) => (
                    <tr key={m.id} className="hover:bg-background-elevated transition-colors">
                      <TD>{m.datamov ?? '—'}</TD>
                      <TD>{m.saida ?? '—'}</TD>
                      <TD>{m.entrada ?? '—'}</TD>
                    </tr>
                  ))}
                </Table>
              )}
            </Secao>
            <Secao titulo="Transferências">
              {transferencias.length === 0 ? (
                <p className="text-sm text-slate-500">Sem transferências.</p>
              ) : (
                <Table head={<><TH>Data</TH><TH>De → Para</TH><TH>Usuário</TH><TH>Obs</TH></>}>
                  {transferencias.map((t) => (
                    <tr key={t.id} className="hover:bg-background-elevated transition-colors">
                      <TD>{formatData(t.data)}</TD>
                      <TD>{(t.de_cliente_nome ?? `#${t.de_cliente}`)} → {(t.para_cliente_nome ?? `#${t.para_cliente}`)}</TD>
                      <TD>{t.usuario_nome ?? '—'}</TD>
                      <TD>{t.obs ?? '—'}</TD>
                    </tr>
                  ))}
                </Table>
              )}
            </Secao>
          </DetailAside>
        </DetailGrid>
      ) : (
        <div className="max-w-3xl">
          <form className="space-y-6" onSubmit={salvar}>{formConteudo}</form>
        </div>
      )}
      {editando && (
        <div className="rounded-2xl bg-background-surface border border-border p-5 space-y-4">
          <h2 className="text-sm font-semibold text-slate-100">Ordens de serviço</h2>
          {ordens.length === 0 ? (
            <p className="text-sm text-slate-500">Nenhuma OS.</p>
          ) : (
            <Table head={<><TH>OS</TH><TH>Chegada</TH><TH>Tipo</TH><TH>Fase</TH><TH>Situação</TH></>}>
              {ordens.map((o) => (
                <tr key={o.id} className="hover:bg-background-elevated transition-colors">
                  <TD><Link to={`/app/ordens/${o.id}`} className="font-semibold text-primary hover:underline">#{o.id}</Link></TD>
                  <TD>{formatData(o.data_chegada)}</TD>
                  <TD>{o.tipo_servico && o.tipo_servico in TIPO_SERVICO ? TIPO_SERVICO[o.tipo_servico as keyof typeof TIPO_SERVICO].label : '—'}</TD>
                  <TD>{o.fase_descricao ? (
                    <span className="inline-flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full" style={{ background: `#${o.fase_cor}` }} />
                      {o.fase_descricao}
                    </span>
                  ) : '—'}</TD>
                  <TD>{o.situacao}</TD>
                </tr>
              ))}
            </Table>
          )}
        </div>
      )}

      {editando && (
        <div className="rounded-2xl bg-background-surface border border-border p-5 space-y-4">
          <h2 className="text-sm font-semibold text-slate-100">Certificados</h2>
          {erroDownload && <p className="text-sm text-danger">{erroDownload}</p>}
          {certs.length === 0 ? (
            <p className="text-sm text-slate-500">Nenhum certificado gerado.</p>
          ) : (
            <Table head={<><TH>OS</TH><TH>Tipo</TH><TH>Gerado em</TH><TH>PDF</TH></>}>
              {certs.map((c) => (
                <tr key={`${c.os}-${c.tipo}`} className="hover:bg-background-elevated transition-colors">
                  <TD><Link to={`/app/ordens/${c.os}`} className="font-semibold text-primary hover:underline">#{c.os}</Link></TD>
                  <TD>{c.tipo === 'C' ? 'Calibração' : 'Manutenção'}</TD>
                  <TD>{formatData(c.data_geracao)}</TD>
                  <TD><button type="button" onClick={() => void baixarPdf(c.os, c.tipo)} className="text-xs font-semibold text-primary hover:underline">Baixar PDF</button></TD>
                </tr>
              ))}
            </Table>
          )}
        </div>
      )}

      {abrindoOS && obj && (
        <AbrirOSModal equipamentoClienteId={obj.id} osAtual={obj.os_atual} onClose={() => setAbrindoOS(false)} />
      )}
      {transferindo && obj && (
        <TransferirModal
          equipamentoClienteId={obj.id}
          donoAtual={obj.cliente}
          onClose={() => setTransferindo(false)}
          onTransferida={() => { setTransferindo(false); setRecarga((n) => n + 1) }}
        />
      )}
    </PageContainer>
  )
}
