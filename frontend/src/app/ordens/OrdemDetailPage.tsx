import { useEffect, useState, type ReactNode } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import {
  IconNote, IconCalendar, IconChart, IconCamera, IconClock,
  IconCheck, IconSearch, IconBattery, IconWrench, IconCaixas, IconX, IconCertificado, IconPencil,
} from '../../components/ui/icons'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { isAdmin, podeAbrirOS, podeMarcarSemConserto, podeEditarTipoServico, podeRegistrarManutencao } from '../../auth/roles'
import { ordensApi, fotosApi, TIPO_SERVICO, FLUXO_FASES, posicaoFase, posLaboratorio, formatData, garantiaBadge, garantiasAtivas, type OrdemDetalhe, type GarantiaItem, type LogOS, type Foto, type OSCertificado, type TipoServico } from './api'
import { GerarCertificadoModal } from './GerarCertificadoModal'
import { LiberarLabModal } from './LiberarLabModal'
import { EditarOSModal } from './EditarOSModal'
import { ManutencaoModal } from './ManutencaoModal'
import { FotoImg } from './FotoImg'
import { FotoLightbox } from './FotoLightbox'
import { PageContainer, DetailGrid, DetailMain, DetailAside } from '../../components/ui/Page'

function Campo({ label, valor }: { label: ReactNode; valor: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] font-medium text-slate-500 uppercase tracking-wide">{label}</dt>
      <dd className="text-sm text-slate-200 mt-0.5 wrap-break-word">{valor ?? '—'}</dd>
    </div>
  )
}

function Secao({ icon, titulo, acao, children }: { icon: ReactNode; titulo: string; acao?: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-2xl bg-background-surface border border-border p-5 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-100">
          <span className="text-slate-500">{icon}</span>
          {titulo}
        </h2>
        {acao}
      </div>
      {children}
    </section>
  )
}

function GarantiaBadge({ item }: { item: GarantiaItem }) {
  const b = garantiaBadge(item)
  return <Badge tone={b.tone}>{b.label}</Badge>
}

function FaseStepper({ faseAtual, cor }: { faseAtual: number | null; cor: string | null }) {
  if (faseAtual === 9) {
    return (
      <div className="inline-flex items-center gap-2 rounded-lg bg-danger/10 border border-danger/30 px-3 py-2 text-sm font-semibold text-danger">
        <IconX className="w-4 h-4" />
        OS cancelada
      </div>
    )
  }
  const posAtual = posicaoFase(faseAtual)
  return (
    <div className="flex items-start overflow-x-auto pb-1">
      {FLUXO_FASES.map((f, i) => {
        const done = posAtual > -1 && i < posAtual
        const atual = i === posAtual
        const corAtual = cor ? `#${cor}` : '#10b981'
        return (
          <div key={f.id} className="flex items-start min-w-0 flex-1">
            <div className="flex flex-col items-center gap-1.5 min-w-16">
              <div
                className={
                  'grid place-items-center w-8 h-8 rounded-full text-xs font-bold shrink-0 transition-colors ' +
                  (done
                    ? 'bg-primary text-white'
                    : atual
                      ? 'text-white'
                      : 'border border-border text-slate-600')
                }
                style={atual ? { backgroundColor: corAtual } : undefined}
              >
                {done ? <IconCheck className="w-4 h-4" /> : i + 1}
              </div>
              <span className={'text-[11px] text-center leading-tight ' + (atual ? 'text-slate-200 font-semibold' : done ? 'text-slate-400' : 'text-slate-600')}>
                {f.nome}
              </span>
            </div>
            {i < FLUXO_FASES.length - 1 && (
              <div className={'h-0.5 flex-1 mt-4 mx-1 rounded-full ' + (i < posAtual ? 'bg-primary' : 'bg-border')} />
            )}
          </div>
        )
      })}
    </div>
  )
}

export function OrdemDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const osId = Number(id)
  const [os, setOs] = useState<OrdemDetalhe | null>(null)
  const [logs, setLogs] = useState<LogOS[]>([])
  const [erro, setErro] = useState('')
  const [carregando, setCarregando] = useState(true)
  const [acao, setAcao] = useState<'gerar' | null>(null)
  const [liberarLabAberto, setLiberarLabAberto] = useState(false)
  const [editarAberto, setEditarAberto] = useState(false)
  const [fotos, setFotos] = useState<Foto[]>([])
  const [certs, setCerts] = useState<OSCertificado[]>([])
  const [erroFoto, setErroFoto] = useState('')
  const [erroCert, setErroCert] = useState('')
  const [erroNF, setErroNF] = useState('')
  const [salvandoTipo, setSalvandoTipo] = useState(false)
  const [erroTipo, setErroTipo] = useState('')
  const [erroObs, setErroObs] = useState('')
  const [obsTexto, setObsTexto] = useState('')
  const [salvandoObs, setSalvandoObs] = useState(false)
  const [lightboxIdx, setLightboxIdx] = useState<number | null>(null)
  const [manutencaoAberta, setManutencaoAberta] = useState(false)

  useEffect(() => {
    let ativo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCarregando(true)
    setErro('')
    Promise.all([ordensApi.obter(osId), ordensApi.logs(osId)])
      .then(([o, l]) => {
        if (!ativo) return
        setOs(o)
        setLogs(l)
      })
      .catch((e) => {
        if (!ativo) return
        setErro(e instanceof ApiError && e.status === 404 ? 'OS não encontrada' : 'Falha ao carregar')
      })
      .finally(() => {
        if (ativo) setCarregando(false)
      })
    return () => {
      ativo = false
    }
  }, [osId])

  function recarregarFotos() {
    return fotosApi.listar(osId).then(setFotos).catch(() => {})
  }

  useEffect(() => {
    let ativo = true
    fotosApi.listar(osId)
      .then((fs) => { if (ativo) setFotos(fs) })
      .catch(() => {})
    ordensApi.certificados(osId)
      .then((cs) => { if (ativo) setCerts(cs) })
      .catch(() => {})
    return () => { ativo = false }
  }, [osId])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setObsTexto(os?.obs ?? '')
  }, [os?.obs])

  if (carregando) return <div className="flex justify-center py-16"><Spinner className="w-8 h-8" /></div>
  if (erro || !os)
    return (
      <div className="px-4 md:px-6 py-6 space-y-4">
        <p className="text-sm text-danger">{erro || 'OS não encontrada'}</p>
        <Button variant="secondary" onClick={() => navigate('/app/ordens')}>Voltar</Button>
      </div>
    )

  const tipo = os.tipo_servico && os.tipo_servico in TIPO_SERVICO ? TIPO_SERVICO[os.tipo_servico as keyof typeof TIPO_SERVICO].label : '—'
  const temCalib = os.calib_cert || os.calib_temp || os.calib_pressao || os.calib_teste_media || os.calib_situacao
  const podeFotos = podeAbrirOS(user)
  const podeGerarCert = isAdmin(user) || user?.funcao === 'Laboratório'
  // Gerar/regerar: do laboratório em diante (calibração já ocorre/ocorreu, inclusive no
  // Financeiro), ou onde já existe certificado. Fora: Recebido (ainda não calibrada) e Cancelada.
  const podeGerarOuRegerar = podeGerarCert && (certs.length > 0 || posLaboratorio(os.fase))
  // Quais seções aparecem — espelha tipos_para no backend.
  const tiposDaOS = os.tipo_servico === 'M' ? ['M'] : os.tipo_servico === 'A' ? ['C', 'M'] : ['C']
  const certDe = (tipo: string) => certs.find((c) => c.tipo === tipo)
  // O aparelho nao tem modelo cadastrado para algum tipo pedido -> nao da para gerar.
  // Avisamos aqui, antes de o usuario tentar (o backend tambem recusa com 409).
  const faltantes = os.certificado_modelos_faltantes ?? []
  const semModelo = faltantes.length > 0
  const modelosFaltantesLabel = faltantes.map((t) => (t === 'C' ? 'Calibração' : 'Manutenção')).join(' e ')
  // A secao aparece do Financeiro em diante — use posicaoFase, NUNCA comparacao numerica (id 10 > 7/8).
  const mostraNotaFiscal = posicaoFase(os.fase) >= posicaoFase(10)
  // Mesmo gate de "Sem conserto": Laboratório ou Admin, só na fase Laboratório (5) e desfecho ainda pendente.
  const podeLiberarLab = os.fase === 5 && os.desfecho_lab === 'pendente' && podeMarcarSemConserto(user)

  function aoLiberarLab() {
    setLiberarLabAberto(false)
    void ordensApi.obter(osId).then(setOs).catch(() => {})
    void ordensApi.logs(osId).then(setLogs).catch(() => {})
  }

  function aoEditarOS() {
    setEditarAberto(false)
    void ordensApi.obter(osId).then(setOs).catch(() => {})
    void ordensApi.logs(osId).then(setLogs).catch(() => {})
  }

  function aoGerarCert(cs: OSCertificado[]) {
    setCerts(cs)
    setAcao(null)
    void ordensApi.obter(osId).then(setOs).catch(() => {})
  }

  async function onBaixarPdf(tipo: 'C' | 'M') {
    setErroCert('')
    try {
      await ordensApi.baixarCertificadoPdf(osId, tipo)
    } catch (e) {
      setErroCert(e instanceof ApiError ? e.message : 'Falha ao baixar PDF')
    }
  }

  async function onBaixarNotaFiscal(tipo: 'pdf' | 'xml' = 'pdf') {
    if (!os) return
    const basename = tipo === 'xml' ? os.nota_fiscal_xml : os.nota_fiscal
    if (!basename) return
    setErroNF('')
    try {
      await ordensApi.baixarNotaFiscal(os.id, basename, tipo)
    } catch (e) {
      setErroNF(e instanceof ApiError ? e.message : 'Falha ao baixar nota fiscal')
    }
  }

  async function onTrocarTipoServico(tipo: TipoServico) {
    setErroTipo('')
    setSalvandoTipo(true)
    try {
      setOs(await ordensApi.editarTipoServico(osId, tipo))
    } catch (err) {
      setErroTipo(err instanceof ApiError ? err.message : 'Falha ao alterar o tipo de serviço')
    } finally {
      setSalvandoTipo(false)
    }
  }

  async function onSalvarObs() {
    setErroObs('')
    setSalvandoObs(true)
    try {
      const atualizado = await ordensApi.editarObservacoes(osId, obsTexto.trim() || null)
      setOs(atualizado)
      // Sincroniza direto da resposta: se o texto so tinha diferenca de espacos
      // (ex.: "nota " -> "nota"), o servidor normaliza para o mesmo valor que
      // ja estava salvo, `os.obs` nao muda e o efeito de sincronizacao (que so
      // dispara quando os.obs muda) nunca re-executaria. Sem isto o botao de
      // salvar ficaria aceso para sempre nesse caso.
      setObsTexto(atualizado.obs ?? '')
    } catch (err) {
      setErroObs(err instanceof ApiError ? err.message : 'Falha ao salvar observações')
    } finally {
      setSalvandoObs(false)
    }
  }

  async function onEnviarFoto(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setErroFoto('')
    try {
      await fotosApi.enviar(osId, file)
      await recarregarFotos()
    } catch (err) {
      setErroFoto(err instanceof ApiError ? err.message : 'Falha ao enviar foto')
    } finally {
      e.target.value = ''
    }
  }

  async function onExcluirFoto(fotoId: number) {
    if (!window.confirm('Excluir esta foto?')) return
    try {
      await fotosApi.excluir(fotoId)
      await recarregarFotos()
    } catch {
      setErroFoto('Falha ao excluir foto')
    }
  }

  return (
    <PageContainer>
      {/* Hero */}
      <div className="rounded-2xl bg-linear-to-br from-background-surface to-background-elevated border border-border p-5 sm:p-6 space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-2xl font-extrabold text-slate-100">OS #{os.id}</h1>
              {os.fase_descricao && (
                <span
                  className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold"
                  style={{ backgroundColor: `#${os.fase_cor}1f`, color: `#${os.fase_cor}` }}
                >
                  <span className="w-1.5 h-1.5 rounded-full" style={{ background: `#${os.fase_cor}` }} />
                  {os.fase_descricao}
                </span>
              )}
              {os.garantias && (
                os.garantias.em_garantia ? (
                  <span className="inline-flex items-center gap-1.5 flex-wrap">
                    <span className="text-xs font-semibold text-slate-400">Garantia:</span>
                    {garantiasAtivas(os.garantias).map((label) => (
                      <Badge key={label} tone="primary">{label}</Badge>
                    ))}
                  </span>
                ) : (
                  <Badge tone="neutral">Sem garantia</Badge>
                )
              )}
            </div>
            <p className="text-sm text-slate-400 mt-2 flex flex-wrap items-center gap-x-2 gap-y-1">
              <Link to={`/app/clientes/${os.cliente}`} className="font-semibold text-slate-200 hover:text-primary hover:underline">{os.cliente_nome ?? '—'}</Link>
              {os.equipamento_descricao && (
                <>
                  <span className="text-slate-600">·</span>
                  {os.equipamento_cliente
                    ? <Link to={`/app/equipamentos/${os.equipamento_cliente}`} className="hover:text-primary hover:underline">{os.equipamento_descricao}</Link>
                    : <span>{os.equipamento_descricao}</span>}
                </>
              )}
              {os.equipamento_serie && <><span className="text-slate-600">·</span><span>Série {os.equipamento_serie}</span></>}
            </p>
          </div>
          <div className="flex gap-2 flex-wrap">
            <Button variant="secondary" onClick={() => navigate('/app/ordens')}>Voltar</Button>
            {isAdmin(user) && (
              <Button variant="secondary" onClick={() => setEditarAberto(true)}>Editar OS</Button>
            )}
            {podeLiberarLab && (
              <Button variant="primary" onClick={() => setLiberarLabAberto(true)}>Liberar do Laboratório</Button>
            )}
          </div>
        </div>
        <div className="pt-5 border-t border-border">
          <FaseStepper faseAtual={os.fase} cor={os.fase_cor} />
        </div>
      </div>

      <DetailGrid>
        <DetailMain>
      {/* Recebimento */}
      <Secao icon={<IconNote className="w-4 h-4" />} titulo="Recebimento">
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-x-4 gap-y-5">
          <Campo
            label="Tipo de serviço"
            valor={
              // O técnico corrige aqui quando encontra na bancada algo que a
              // Expedição não tinha como ver na entrada. Fora do laboratório
              // continua sendo só leitura.
              podeEditarTipoServico(user, os.fase) ? (
                <div className="space-y-1">
                  <label htmlFor="os-tipo-servico" className="sr-only">Tipo de serviço</label>
                  <select
                    id="os-tipo-servico"
                    value={os.tipo_servico ?? ''}
                    disabled={salvandoTipo}
                    onChange={(e) => onTrocarTipoServico(e.target.value as TipoServico)}
                    className="w-full rounded-lg bg-background border border-border px-2 py-1 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-60"
                  >
                    {Object.entries(TIPO_SERVICO).map(([valor, { label }]) => (
                      <option key={valor} value={valor}>{label}</option>
                    ))}
                  </select>
                  {erroTipo && <p className="text-xs text-danger">{erroTipo}</p>}
                </div>
              ) : tipo
            }
          />
          <Campo label="Condição de chegada" valor={os.condicao_chegada ? <Badge tone="neutral">{os.condicao_chegada}</Badge> : '—'} />
          <Campo label="Data de chegada" valor={formatData(os.data_chegada)} />
          <Campo
            label="Caixa"
            valor={os.caixa
              ? <Link to={`/app/caixas/${os.caixa}`} className="inline-flex items-center gap-1 text-primary hover:underline"><IconCaixas className="w-3.5 h-3.5" />#{os.caixa}</Link>
              : '—'}
          />
          <Campo label={<span className="inline-flex items-center gap-1"><IconBattery className="w-3 h-3" />Pilhas</span>} valor={os.pilhas} />
          <Campo label={<span className="inline-flex items-center gap-1"><IconWrench className="w-3 h-3" />Bocais</span>} valor={os.bocais} />
        </div>
        <div>
          <dt className="text-[11px] font-medium text-slate-500 uppercase tracking-wide mb-1.5">Acessórios</dt>
          {os.acessorios_presentes.length ? (
            <div className="flex flex-wrap gap-1.5">
              {os.acessorios_presentes.map((a) => (
                <span key={a} className="rounded-full bg-primary/15 text-primary border border-primary/30 px-2.5 py-1 text-xs">{a}</span>
              ))}
            </div>
          ) : (
            <span className="text-sm text-slate-500">—</span>
          )}
        </div>
      </Secao>

      {/* Observações */}
      <Secao
        icon={<IconPencil className="w-4 h-4" />}
        titulo="Observações"
        acao={
          <button
            type="button"
            onClick={onSalvarObs}
            disabled={salvandoObs || obsTexto === (os.obs ?? '')}
            className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold bg-primary text-white hover:bg-primary-600 disabled:opacity-50 transition-colors"
          >
            Salvar observações
          </button>
        }
      >
        <label htmlFor="os-obs" className="sr-only">Observações</label>
        <textarea
          id="os-obs"
          value={obsTexto}
          onChange={(e) => { setObsTexto(e.target.value); setErroObs('') }}
          disabled={salvandoObs}
          rows={4}
          placeholder="Anotações sobre esta OS — visíveis para toda a equipe, em qualquer fase."
          className="w-full rounded-lg bg-background border border-border px-3 py-2 text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-60"
        />
        {erroObs && <p className="text-sm text-danger">{erroObs}</p>}
      </Secao>

      {/* Fotos */}
      <Secao
        icon={<IconCamera className="w-4 h-4" />}
        titulo="Fotos"
        acao={podeFotos && (
          <label className="cursor-pointer">
            <span className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold bg-primary text-white hover:bg-primary-600 transition-colors">
              <IconCamera className="w-3.5 h-3.5" /> Enviar foto
            </span>
            <input type="file" accept="image/*" className="hidden" onChange={onEnviarFoto} />
          </label>
        )}
      >
        {erroFoto && <p className="text-sm text-danger">{erroFoto}</p>}
        {fotos.length === 0 ? (
          <p className="text-sm text-slate-500">Nenhuma foto.</p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {fotos.map((f, idx) => (
              <div key={f.id} className="group relative">
                <button
                  type="button"
                  onClick={() => setLightboxIdx(idx)}
                  className="block w-full overflow-hidden rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary"
                  aria-label="Ampliar foto"
                >
                  <FotoImg url={f.url} alt={f.legenda ?? 'foto'} className="w-full h-32 object-cover transition-transform duration-200 group-hover:scale-105" />
                  <span className="absolute inset-0 grid place-items-center bg-black/0 group-hover:bg-black/40 opacity-0 group-hover:opacity-100 transition-all">
                    <IconSearch className="w-6 h-6 text-white" />
                  </span>
                </button>
                {f.legenda && <p className="text-xs text-slate-500 truncate mt-1">{f.legenda}</p>}
                {podeFotos && (
                  <button
                    type="button"
                    onClick={() => void onExcluirFoto(f.id)}
                    aria-label="Excluir foto"
                    className="absolute top-1.5 right-1.5 grid place-items-center w-7 h-7 rounded-lg bg-black/50 text-white opacity-0 group-hover:opacity-100 hover:bg-danger transition-all"
                  >
                    <IconX className="w-4 h-4" />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </Secao>

      {/* Datas */}
      <Secao icon={<IconCalendar className="w-4 h-4" />} titulo="Datas">
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-x-4 gap-y-5">
          <Campo label="Calibração" valor={formatData(os.data_calibracao)} />
          <Campo label="Aceite" valor={formatData(os.data_aceite)} />
          <Campo label="Retorno (postagem)" valor={formatData(os.data_retorno)} />
          <Campo label="Próxima calibração" valor={formatData(os.prox_calibragem)} />
        </div>
      </Secao>

      {/* Garantia */}
      {os.garantias && (
        <Secao icon={<IconCheck className="w-4 h-4" />} titulo="Garantia">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-x-4 gap-y-5">
            <Campo label="Calibração" valor={<GarantiaBadge item={os.garantias.calibracao} />} />
            <Campo label="Manutenção" valor={<GarantiaBadge item={os.garantias.manutencao} />} />
            <Campo label="Compra" valor={<GarantiaBadge item={os.garantias.compra} />} />
          </div>
        </Secao>
      )}

      {/* Resultados da calibração */}
      <Secao
        icon={<IconChart className="w-4 h-4" />}
        titulo="Resultados da calibração"
      >
        {temCalib ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-x-4 gap-y-5">
            <Campo label="Certificado" valor={os.calib_cert} />
            <Campo label="Temperatura" valor={os.calib_temp} />
            <Campo label="Pressão" valor={os.calib_pressao} />
            <Campo label="Média dos testes" valor={os.calib_teste_media} />
            <Campo label="Situação" valor={os.calib_situacao} />
          </div>
        ) : (
          <p className="text-sm text-slate-500">Sem resultados de calibração ainda.</p>
        )}
        {erroCert && <p className="text-sm text-danger">{erroCert}</p>}
      </Secao>
        </DetailMain>
        <DetailAside>
      {/* Uma seção por documento: deixa explícito qual está sendo feito e onde. */}
      {tiposDaOS.includes('C') && (
        <Secao
          icon={<IconCertificado className="w-4 h-4" />}
          titulo="Certificado de calibração"
          acao={podeGerarOuRegerar && !semModelo && (
            <Button variant={certDe('C') ? 'secondary' : 'primary'} onClick={() => setAcao('gerar')}>
              {certDe('C') ? 'Regerar certificado' : 'Gerar certificado'}
            </Button>
          )}
        >
          {/* O aviso ACOMPANHA a lista, nunca a substitui: o documento já emitido
              não pode sumir da tela por falta de modelo de outro tipo. */}
          {semModelo && (
            <div className="rounded-lg bg-warning/10 border border-warning/20 px-3 py-2.5 space-y-1.5">
              <p className="text-sm text-warning">
                Este aparelho não tem modelo de certificado de {modelosFaltantesLabel} cadastrado — por isso não é
                possível gerar o certificado.
              </p>
              <Link to="/app/certificados" className="inline-block text-xs font-semibold text-primary hover:underline">
                Cadastrar modelo de certificado
              </Link>
            </div>
          )}
          {os.desfecho_lab === 'liberado' && (
            <p className="text-sm text-slate-400">Liberado sem certificado{os.desfecho_lab_obs ? ` — ${os.desfecho_lab_obs}` : ''}.</p>
          )}
          {certDe('C') ? (
            <div className="flex items-center justify-between rounded-lg border border-border px-3 py-2">
              <span className="text-sm text-slate-200">
                Gerado <span className="text-xs text-slate-500 ml-1">{formatData(certDe('C')!.data_geracao)}</span>
              </span>
              <button type="button" onClick={() => void onBaixarPdf('C')} className="text-xs font-semibold text-primary hover:underline">Baixar PDF</button>
            </div>
          ) : (
            <p className="text-sm text-slate-500">Nenhum certificado de calibração gerado.</p>
          )}
        </Secao>
      )}

      {tiposDaOS.includes('M') && (
        <Secao
          icon={<IconCertificado className="w-4 h-4" />}
          titulo="Certificado de manutenção"
          acao={podeRegistrarManutencao(user, os.fase) && (
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setManutencaoAberta(true)}>Registrar manutenção</Button>
              {!semModelo && (
                <Button variant={certDe('M') ? 'secondary' : 'primary'} onClick={() => setAcao('gerar')}>
                  {certDe('M') ? 'Regerar relatório' : 'Gerar relatório'}
                </Button>
              )}
            </div>
          )}
        >
          {certDe('M') ? (
            <div className="flex items-center justify-between rounded-lg border border-border px-3 py-2">
              <span className="text-sm text-slate-200">
                Gerado <span className="text-xs text-slate-500 ml-1">{formatData(certDe('M')!.data_geracao)}</span>
              </span>
              <button type="button" onClick={() => void onBaixarPdf('M')} className="text-xs font-semibold text-primary hover:underline">Baixar PDF</button>
            </div>
          ) : (
            <p className="text-sm text-slate-500">
              Nenhum relatório de manutenção gerado. Registre a manutenção antes de gerar.
            </p>
          )}
        </Secao>
      )}

      {/* Nota fiscal — só exibição/download; o anexo é feito no nível da caixa
          (CaixaDetailPage), de uma vez para todas as OS ativas, não mais por OS aqui. */}
      {mostraNotaFiscal && (
        <Secao
          icon={<IconCertificado className="w-4 h-4" />}
          titulo="Nota fiscal"
        >
          {os.nota_fiscal ? (
            <div className="flex items-center justify-between gap-3">
              <Campo label="Número" valor={os.nota_fiscal_numero} />
              <div className="flex items-center gap-3">
                <button
                  onClick={() => onBaixarNotaFiscal('pdf')}
                  className="text-xs font-semibold text-primary hover:underline"
                >
                  Baixar PDF
                </button>
                {/* OS antigas foram anexadas quando havia um arquivo so, entao
                    nem toda nota tem XML — o botao so aparece quando existe. */}
                {os.nota_fiscal_xml && (
                  <button
                    onClick={() => onBaixarNotaFiscal('xml')}
                    className="text-xs font-semibold text-primary hover:underline"
                  >
                    Baixar XML
                  </button>
                )}
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-500">
              Nenhuma nota fiscal anexada ainda — é anexada na tela da caixa (fase Financeiro), para
              todas as OS de uma vez.
            </p>
          )}
          {erroNF && <p className="text-sm text-danger">{erroNF}</p>}
        </Secao>
      )}

      {/* Histórico */}
      <Secao icon={<IconClock className="w-4 h-4" />} titulo="Histórico">
        {logs.length === 0 ? (
          <p className="text-sm text-slate-500">Sem eventos.</p>
        ) : (
          <ol>
            {logs.map((l, i) => (
              <li key={l.id} className="flex gap-3">
                <div className="flex flex-col items-center">
                  <span className="w-2.5 h-2.5 rounded-full bg-primary mt-1.5 shrink-0" />
                  {i < logs.length - 1 && <span className="w-px flex-1 bg-border my-1" />}
                </div>
                <div className="pb-4">
                  <p className="text-sm text-slate-200">{l.texto ?? '—'}</p>
                  <p className="text-xs text-slate-500 mt-0.5">{formatData(l.datalog)}</p>
                </div>
              </li>
            ))}
          </ol>
        )}
      </Secao>
        </DetailAside>
      </DetailGrid>

      {acao === 'gerar' && <GerarCertificadoModal os={os} onClose={() => setAcao(null)} onGerado={aoGerarCert} />}

      {liberarLabAberto && (
        <LiberarLabModal osId={osId} onClose={() => setLiberarLabAberto(false)} onConcluido={aoLiberarLab} />
      )}

      {editarAberto && (
        <EditarOSModal os={os} onClose={() => setEditarAberto(false)} onSalvo={aoEditarOS} />
      )}

      {manutencaoAberta && (
        <ManutencaoModal
          osId={osId}
          onClose={() => setManutencaoAberta(false)}
          onSalvo={() => { void ordensApi.obter(osId).then(setOs) }}
        />
      )}

      {lightboxIdx !== null && fotos[lightboxIdx] && (
        <FotoLightbox fotos={fotos} indiceInicial={lightboxIdx} onClose={() => setLightboxIdx(null)} />
      )}
    </PageContainer>
  )
}
