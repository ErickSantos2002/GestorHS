import { useEffect, useState, type ReactNode } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import {
  IconNote, IconCalendar, IconChart, IconCamera, IconClock,
  IconCheck, IconSearch, IconBattery, IconWrench, IconCaixas, IconX, IconCertificado,
} from '../../components/ui/icons'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { isAdmin, podeAbrirOS, podeAnexarNotaFiscal } from '../../auth/roles'
import { fasesApi, type Fase } from '../cadastros/api'
import { ordensApi, fotosApi, buscarBlobUrl, TIPO_SERVICO, TRANSICOES, FLUXO_FASES, posicaoFase, faseAtiva, posLaboratorio, formatData, garantiaBadge, garantiasAtivas, type OrdemDetalhe, type GarantiaItem, type LogOS, type Foto, type OSCertificado } from './api'
import { AvancarModal } from './AvancarModal'
import { GerarCertificadoModal } from './GerarCertificadoModal'
import { CancelarModal } from './CancelarModal'
import { NotaFiscalModal } from './NotaFiscalModal'
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
  const [fases, setFases] = useState<Fase[]>([])
  const [erro, setErro] = useState('')
  const [carregando, setCarregando] = useState(true)
  const [acao, setAcao] = useState<'avancar' | 'cancelar' | 'gerar' | 'nota-fiscal' | null>(null)
  const [fotos, setFotos] = useState<Foto[]>([])
  const [certs, setCerts] = useState<OSCertificado[]>([])
  const [erroFoto, setErroFoto] = useState('')
  const [erroCert, setErroCert] = useState('')
  const [lightboxIdx, setLightboxIdx] = useState<number | null>(null)

  useEffect(() => {
    let ativo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCarregando(true)
    setErro('')
    Promise.all([ordensApi.obter(osId), ordensApi.logs(osId), fasesApi.listar()])
      .then(([o, l, fs]) => {
        if (!ativo) return
        setOs(o)
        setLogs(l)
        setFases(fs)
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

  function aoConcluir(novaOS: OrdemDetalhe) {
    setOs(novaOS)
    setAcao(null)
    void ordensApi.logs(osId).then(setLogs).catch(() => {})
  }

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
  const faseAtual = fases.find((f) => f.id === os.fase)
  const responsavelNome = faseAtual?.funcao_nome ?? null
  const podeAgir = isAdmin(user) || (!!responsavelNome && user?.funcao === responsavelNome)
  const ativa = faseAtiva(os.fase)
  const transicao = os.fase != null ? TRANSICOES[os.fase] : undefined
  const podeFotos = podeAbrirOS(user)
  const podeGerarCert = isAdmin(user) || user?.funcao === 'Laboratório'
  // Gerar/regerar: do laboratório em diante (calibração já ocorre/ocorreu, inclusive no
  // Financeiro), ou onde já existe certificado. Fora: Recebido (ainda não calibrada) e Cancelada.
  const podeGerarOuRegerar = podeGerarCert && (certs.length > 0 || posLaboratorio(os.fase))
  // A secao aparece do Financeiro em diante — use posicaoFase, NUNCA comparacao numerica (id 10 > 7/8).
  const mostraNotaFiscal = posicaoFase(os.fase) >= posicaoFase(10)
  const podeAnexarNF = podeAnexarNotaFiscal(user)

  function aoGerarCert(cs: OSCertificado[]) {
    setCerts(cs)
    setAcao(null)
    void ordensApi.obter(osId).then(setOs).catch(() => {})
  }

  function aoAnexarNF() {
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
            {ativa && podeAgir && transicao && <Button onClick={() => setAcao('avancar')}>{transicao.rotulo}</Button>}
            {ativa && podeAgir && <Button variant="danger" onClick={() => setAcao('cancelar')}>Cancelar OS</Button>}
            <Button variant="secondary" onClick={() => navigate('/app/ordens')}>Voltar</Button>
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
          <Campo label="Tipo de serviço" valor={tipo} />
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
        {os.obs && (
          <div>
            <dt className="text-[11px] font-medium text-slate-500 uppercase tracking-wide mb-1">Observações</dt>
            <dd className="text-sm text-slate-200 whitespace-pre-wrap">{os.obs}</dd>
          </div>
        )}
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
      {/* Certificados gerados */}
      <Secao
        icon={<IconCertificado className="w-4 h-4" />}
        titulo="Certificados"
        acao={podeGerarOuRegerar && (
          <Button variant={certs.length ? 'secondary' : 'primary'} onClick={() => setAcao('gerar')}>
            {certs.length ? 'Regerar certificado' : 'Gerar certificado de calibração'}
          </Button>
        )}
      >
        {certs.length === 0 ? (
          <p className="text-sm text-slate-500">Nenhum certificado gerado.{podeGerarOuRegerar ? ' Clique em "Gerar certificado de calibração".' : ''}</p>
        ) : (
          <ul className="space-y-2">
            {certs.map((c) => (
              <li key={c.tipo} className="flex items-center justify-between rounded-lg border border-border px-3 py-2">
                <span className="text-sm text-slate-200">
                  {c.tipo === 'C' ? 'Calibração' : 'Manutenção'}
                  <span className="text-xs text-slate-500 ml-2">{formatData(c.data_geracao)}</span>
                </span>
                <button type="button" onClick={() => void onBaixarPdf(c.tipo)} className="text-xs font-semibold text-primary hover:underline">Baixar PDF</button>
              </li>
            ))}
          </ul>
        )}
      </Secao>

      {/* Nota fiscal */}
      {mostraNotaFiscal && (
        <Secao
          icon={<IconCertificado className="w-4 h-4" />}
          titulo="Nota fiscal"
          acao={podeAnexarNF ? (
            <Button variant={os.nota_fiscal ? 'secondary' : 'primary'} onClick={() => setAcao('nota-fiscal')}>
              {os.nota_fiscal ? 'Substituir' : 'Anexar nota fiscal'}
            </Button>
          ) : undefined}
        >
          {os.nota_fiscal ? (
            <div className="flex items-center justify-between gap-3">
              <Campo label="Número" valor={os.nota_fiscal_numero} />
              <button
                onClick={async () => {
                  const url = await buscarBlobUrl(`/ordens/${os.id}/nota-fiscal`)
                  window.open(url, '_blank')
                }}
                className="text-xs font-semibold text-primary hover:underline"
              >
                Baixar
              </button>
            </div>
          ) : (
            <p className="text-sm text-slate-500">
              Nenhuma nota fiscal anexada. É obrigatória para o Financeiro confirmar o pagamento.
            </p>
          )}
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

      {acao === 'avancar' && transicao && (
        <AvancarModal os={os} rotulo={transicao.rotulo} pedeCodRetorno={transicao.pedeCodRetorno} pedeProxCalibragem={transicao.pedeProxCalibragem} onClose={() => setAcao(null)} onConcluido={aoConcluir} />
      )}
      {acao === 'gerar' && <GerarCertificadoModal os={os} onClose={() => setAcao(null)} onGerado={aoGerarCert} />}
      {acao === 'cancelar' && <CancelarModal os={os} onClose={() => setAcao(null)} onConcluido={aoConcluir} />}
      {acao === 'nota-fiscal' && (
        <NotaFiscalModal ordemId={os.id} onClose={() => setAcao(null)} onEnviado={aoAnexarNF} />
      )}

      {lightboxIdx !== null && fotos[lightboxIdx] && (
        <FotoLightbox fotos={fotos} indiceInicial={lightboxIdx} onClose={() => setLightboxIdx(null)} />
      )}
    </PageContainer>
  )
}
