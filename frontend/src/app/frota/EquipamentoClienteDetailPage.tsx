import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { Toggle } from '../../components/ui/Toggle'
import { Table, TH, TD } from '../../components/ui/Table'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { isAdmin, podeAbrirOS, podeEditarCadastros, podeGerenciarCadastros, podeGerarCertificadoVenda } from '../../auth/roles'
import { AbrirOSModal } from '../ordens/AbrirOSModal'
import { TransferirModal } from './TransferirModal'
import { CertificadoVendaModal } from './CertificadoVendaModal'
import { ordensApi, formatData, osAtiva, TIPO_SERVICO, type OrdemListItem } from '../ordens/api'
import { equipamentosClienteApi, STATUS_CALIBRACAO, type EquipamentoCliente, type EquipamentoClientePayload, type Historico, type StatusCalibracao, type EquipCertItem, type Transferencia } from './api'
import { equipamentosApi, type Equipamento } from '../cadastros/api'
import { PageContainer, DetailGrid, DetailMain, DetailAside } from '../../components/ui/Page'
import { hojeISO, daquiAAnos } from '../../lib/datas'

const VAZIO: EquipamentoClientePayload = {
  cliente: 0, equipamento: 0, modulo: 0, serie: null, patrimonio: null,
  datacompra: null, ult_calibragem: null, prox_calibragem: null, ativo: true,
}

/** Aparelho novo ja nasce com as datas do caso comum: cadastrado no dia da
 *  compra/calibragem, com validade de um ano. Sao so valores iniciais — o
 *  usuario sobrescreve quando o aparelho for antigo. */
function datasPadrao(): Pick<EquipamentoClientePayload, 'datacompra' | 'ult_calibragem' | 'prox_calibragem'> {
  return { datacompra: hojeISO(), ult_calibragem: hojeISO(), prox_calibragem: daquiAAnos(1) }
}

function Secao({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <div className="rounded-2xl bg-background-surface border border-border p-5 space-y-4">
      <h2 className="text-sm font-semibold text-slate-100">{titulo}</h2>
      {children}
    </div>
  )
}

function Provenancia({ entrouEm, origem }: { entrouEm: string | null; origem: string | null }) {
  if (!entrouEm && !origem) return null
  return (
    <p className="text-xs text-slate-500">
      {entrouEm && `Registrado em ${formatData(entrouEm)}`}
      {entrouEm && origem && ' · '}
      {origem}
    </p>
  )
}

export function EquipamentoClienteDetailPage({ embutido = false }: { embutido?: boolean } = {}) {
  const params = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const aparelhoId = embutido ? params.aparelho : params.id
  const editando = aparelhoId !== undefined
  const podeEditar = editando ? podeEditarCadastros(user) : podeGerenciarCadastros(user)
  const clienteParam = searchParams.get('cliente')
  const clienteId = embutido ? Number(params.id) : (clienteParam ? Number(clienteParam) : 0)
  const voltarBase = embutido ? `/app/clientes/${clienteId}/equipamentos` : '/app/equipamentos'

  const [form, setForm] = useState<EquipamentoClientePayload>(
    // no modo edicao o efeito abaixo sobrescreve tudo com o que veio do servidor
    { ...VAZIO, cliente: clienteId, ...(editando ? {} : datasPadrao()) },
  )
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
  const [gerandoVenda, setGerandoVenda] = useState(false)
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
      .obter(Number(aparelhoId))
      .then((e) => {
        if (!ativo) return
        setObj(e)
        setForm({
          cliente: e.cliente, equipamento: e.equipamento, modulo: e.modulo, serie: e.serie, patrimonio: e.patrimonio,
          datacompra: e.datacompra, ult_calibragem: e.ult_calibragem, prox_calibragem: e.prox_calibragem,
          ativo: e.ativo,
        })
      })
      .catch((err) => {
        if (ativo) setErro(err instanceof ApiError ? err.message : 'Falha ao carregar')
      })
      .finally(() => {
        if (ativo) setCarregando(false)
      })
    void equipamentosClienteApi.historico(Number(aparelhoId)).then((h) => { if (ativo) setHistorico(h) }).catch(() => {})
    void equipamentosClienteApi.ordens(Number(aparelhoId)).then((o) => { if (ativo) setOrdens(o) }).catch(() => {})
    void equipamentosClienteApi.certificados(Number(aparelhoId)).then((c) => { if (ativo) setCerts(c) }).catch(() => {})
    void equipamentosClienteApi.transferencias(Number(aparelhoId)).then((t) => { if (ativo) setTransferencias(t) }).catch(() => {})
    return () => {
      ativo = false
    }
  }, [aparelhoId, editando, recarga])

  function set<K extends keyof EquipamentoClientePayload>(chave: K, valor: EquipamentoClientePayload[K]) {
    setForm((f) => ({ ...f, [chave]: valor }))
  }

  async function salvar(e: FormEvent) {
    e.preventDefault(); setErro(''); setEnviando(true)
    try {
      if (editando) {
        const { cliente: _c, ...resto } = form
        void _c
        const atualizado = await equipamentosClienteApi.atualizar(Number(aparelhoId), resto)
        setObj(atualizado)
      } else {
        const novo = await equipamentosClienteApi.criar(form)
        navigate(`${voltarBase}/${novo.id}`, { replace: true })
        return
      }
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao salvar')
    } finally {
      setEnviando(false)
    }
  }

  async function baixarPdf(c: EquipCertItem) {
    setErroDownload('')
    try {
      if (c.origem === 'venda') {
        await equipamentosClienteApi.baixarCertificadoVendaPdf(Number(aparelhoId))
      } else {
        await ordensApi.baixarCertificadoPdf(c.os!, c.tipo)
      }
    } catch {
      setErroDownload('Falha ao baixar PDF')
    }
  }

  async function excluir() {
    if (!editando) return
    if (!window.confirm('Excluir este aparelho?')) return
    setErro('')
    try {
      await equipamentosClienteApi.excluir(Number(aparelhoId))
      navigate(voltarBase, { replace: true })
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
        <p className="text-sm text-slate-400">Abra a partir dos equipamentos de um cliente para cadastrar um aparelho.</p>
        <Button variant="secondary" className="mt-3" onClick={() => navigate(voltarBase)}>Ir para os Equipamentos</Button>
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
          <div className="flex items-center gap-3 text-sm text-slate-300 sm:self-end sm:pb-2">
            <Toggle checked={form.ativo} onChange={(v) => set('ativo', v)} label="Ativo" disabled={ro} />
            <span>{form.ativo ? 'Ativo' : 'Inativo'}</span>
          </div>
        </div>
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

  const corpo = (
    <>
      {embutido && (
        <p className="text-sm text-slate-400">
          <Link to={voltarBase} className="hover:underline">Equipamentos</Link>
          {' › '}{editando ? (obj?.equipamento_descricao || 'Aparelho') : 'Novo aparelho'}
        </p>
      )}
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
          {editando && podeGerenciarCadastros(user) && (
            <Button
              variant="secondary"
              onClick={() => setTransferindo(true)}
              disabled={!!osEmAndamento}
              title={osEmAndamento ? 'Finalize a OS em andamento antes de transferir' : undefined}
            >
              Transferir
            </Button>
          )}
          {editando && isAdmin(user) && <Button variant="danger" onClick={excluir}>Excluir</Button>}
          <Button variant="secondary" onClick={() => navigate(voltarBase)}>Voltar</Button>
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
            {/* O elo Phoebus<->Módulo é sempre um dos três estados abaixo — nunca dois ao mesmo tempo
                (invariante do backend: um aparelho não pode ser simultaneamente um Phoebus com módulo
                instalado e um módulo instalado em outro lugar). Encadeado como else-if para deixar
                essa exclusividade explícita mesmo se o invariante um dia falhar. */}
            {obj?.modulo_instalado ? (
              <Secao titulo="Módulo instalado">
                <p className="text-sm text-slate-300">
                  <Link to={`/app/equipamentos/${obj.modulo_instalado.id}`} className="text-primary hover:underline">
                    {obj.modulo_instalado.serie || `#${obj.modulo_instalado.id}`}
                  </Link>
                </p>
                <Provenancia entrouEm={obj.modulo_instalado.entrou_em} origem={obj.modulo_instalado.origem} />
              </Secao>
            ) : obj?.instalado_em ? (
              <Secao titulo="Instalado em">
                <p className="text-sm text-slate-300">
                  <Link to={`/app/equipamentos/${obj.instalado_em.id}`} className="text-primary hover:underline">
                    {obj.instalado_em.serie || `#${obj.instalado_em.id}`}
                  </Link>
                  {obj.instalado_em.cliente_nome && <span className="text-slate-500"> · {obj.instalado_em.cliente_nome}</span>}
                </p>
                <Provenancia entrouEm={obj.instalado_em.entrou_em} origem={obj.instalado_em.origem} />
              </Secao>
            ) : obj?.em_estoque ? (
              <Secao titulo="No estoque">
                <p className="text-sm text-slate-300">Módulo sem instalação em aberto.</p>
              </Secao>
            ) : null}

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
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-sm font-semibold text-slate-100">Certificados</h2>
            {podeGerarCertificadoVenda(user) && (
              <button
                type="button"
                onClick={() => setGerandoVenda(true)}
                className="text-xs font-semibold text-primary hover:underline"
              >
                {certs.some((c) => c.origem === 'venda') ? 'Regerar certificado de venda' : 'Gerar certificado de venda'}
              </button>
            )}
          </div>
          {erroDownload && <p className="text-sm text-danger">{erroDownload}</p>}
          {certs.length === 0 ? (
            <p className="text-sm text-slate-500">Nenhum certificado gerado.</p>
          ) : (
            <Table head={<><TH>OS</TH><TH>Tipo</TH><TH>Gerado em</TH><TH>PDF</TH></>}>
              {certs.map((c) => (
                <tr key={c.origem === 'venda' ? 'venda' : `${c.os}-${c.tipo}`} className="hover:bg-background-elevated transition-colors">
                  <TD>{c.origem === 'venda'
                    ? <span className="text-slate-400">— Venda</span>
                    : <Link to={`/app/ordens/${c.os}`} className="font-semibold text-primary hover:underline">#{c.os}</Link>}</TD>
                  <TD>{c.tipo === 'C' ? 'Calibração' : 'Manutenção'}</TD>
                  <TD>{formatData(c.data_geracao)}</TD>
                  <TD><button type="button" onClick={() => void baixarPdf(c)} className="text-xs font-semibold text-primary hover:underline">Baixar PDF</button></TD>
                </tr>
              ))}
            </Table>
          )}
        </div>
      )}

      {abrindoOS && obj && (
        <AbrirOSModal equipamentoClienteId={obj.id} osAtual={obj.os_atual} onClose={() => setAbrindoOS(false)} />
      )}
      {gerandoVenda && obj && (
        <CertificadoVendaModal
          aparelhoId={obj.id}
          onClose={() => setGerandoVenda(false)}
          onGerado={() => { setGerandoVenda(false); setRecarga((n) => n + 1) }}
        />
      )}
      {transferindo && obj && (
        <TransferirModal
          equipamentoClienteId={obj.id}
          donoAtual={obj.cliente}
          onClose={() => setTransferindo(false)}
          onTransferida={() => { setTransferindo(false); setRecarga((n) => n + 1) }}
        />
      )}
    </>
  )

  return embutido ? corpo : <PageContainer>{corpo}</PageContainer>
}
