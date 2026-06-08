import { useEffect, useState, type ReactNode } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { isAdmin, podeAbrirOS } from '../../auth/roles'
import { fasesApi, type Fase } from '../cadastros/api'
import { ordensApi, fotosApi, certificadoApi, TIPO_SERVICO, TRANSICOES, formatData, type OrdemDetalhe, type LogOS, type Foto } from './api'
import { AvancarModal } from './AvancarModal'
import { CancelarModal } from './CancelarModal'
import { FotoImg } from './FotoImg'

function Campo({ label, valor }: { label: string; valor: ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="text-sm text-slate-200">{valor ?? '—'}</dd>
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
  const [acao, setAcao] = useState<'avancar' | 'cancelar' | null>(null)
  const [fotos, setFotos] = useState<Foto[]>([])
  const [erroFoto, setErroFoto] = useState('')
  const [erroCert, setErroCert] = useState('')

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
  const temCalib = os.calib_cert || os.calib_temp || os.calib_pressao || os.calib_teste_media || os.calib_situacao || os.pdf_certificado
  const faseAtual = fases.find((f) => f.id === os.fase)
  const responsavelNome = faseAtual?.funcao_nome ?? null
  const podeAgir = isAdmin(user) || (!!responsavelNome && user?.funcao === responsavelNome)
  const ativa = os.fase != null && os.fase >= 4 && os.fase <= 7
  const transicao = os.fase != null ? TRANSICOES[os.fase] : undefined
  const podeFotos = podeAbrirOS(user)
  const podeCertificado = isAdmin(user) || user?.funcao === 'Laboratório'

  async function onEnviarCertificado(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setErroCert('')
    try {
      await certificadoApi.enviar(osId, file)
      const o = await ordensApi.obter(osId)
      setOs(o)
    } catch (err) {
      setErroCert(err instanceof ApiError ? err.message : 'Falha ao enviar certificado')
    } finally {
      e.target.value = ''
    }
  }

  async function onBaixarCertificado() {
    try {
      await certificadoApi.baixar(osId)
    } catch {
      setErroCert('Falha ao baixar certificado')
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
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-extrabold text-slate-100">OS #{os.id}</h1>
          {os.fase_descricao && (
            <Badge tone="neutral">
              <span className="inline-flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full" style={{ background: `#${os.fase_cor}` }} />
                {os.fase_descricao}
              </span>
            </Badge>
          )}
        </div>
        <div className="flex gap-2">
          {ativa && podeAgir && transicao && <Button onClick={() => setAcao('avancar')}>{transicao.rotulo}</Button>}
          {ativa && podeAgir && <Button variant="danger" onClick={() => setAcao('cancelar')}>Cancelar OS</Button>}
          <Button variant="secondary" onClick={() => navigate('/app/ordens')}>Voltar</Button>
        </div>
      </div>

      <section className="rounded-2xl bg-background-surface border border-border p-5 grid grid-cols-2 md:grid-cols-4 gap-4">
        <Campo label="Cliente" valor={os.cliente_nome} />
        <Campo label="Equipamento" valor={os.equipamento_descricao} />
        <Campo label="Série" valor={os.equipamento_serie} />
        <Campo label="Situação" valor={os.situacao} />
      </section>

      <section className="rounded-2xl bg-background-surface border border-border p-5 space-y-3">
        <h2 className="text-sm font-semibold text-slate-100">Recebimento</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Campo label="Tipo de serviço" valor={tipo} />
          <Campo label="Condição de chegada" valor={os.condicao_chegada} />
          <Campo label="Acessórios" valor={os.acessorios_presentes.length ? os.acessorios_presentes.join(', ') : '—'} />
          <Campo label="Pilhas" valor={os.pilhas} />
          <Campo label="Bocais" valor={os.bocais} />
          <Campo label="Observações" valor={os.obs || '—'} />
          <Campo label="Data de chegada" valor={formatData(os.data_chegada)} />
          {os.caixa && (
            <Campo
              label="Caixa"
              valor={<Link to={`/app/caixas/${os.caixa}`} className="text-primary hover:underline">#{os.caixa}</Link>}
            />
          )}
        </div>
      </section>

      <section className="rounded-2xl bg-background-surface border border-border p-5 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-100">Fotos</h2>
          {podeFotos && (
            <label className="cursor-pointer">
              <span className="inline-flex items-center rounded-lg px-3 py-1.5 text-xs font-medium bg-primary text-white hover:opacity-90 transition-opacity">
                Enviar foto
              </span>
              <input type="file" accept="image/*" className="hidden" onChange={onEnviarFoto} />
            </label>
          )}
        </div>
        {erroFoto && <p className="text-sm text-danger">{erroFoto}</p>}
        {fotos.length === 0 ? (
          <p className="text-sm text-slate-500">Nenhuma foto.</p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {fotos.map((f) => (
              <div key={f.id} className="flex flex-col gap-1">
                <FotoImg url={f.url} alt={f.legenda ?? 'foto'} className="w-full h-28 object-cover rounded-lg" />
                {f.legenda && <p className="text-xs text-slate-500 truncate">{f.legenda}</p>}
                {podeFotos && (
                  <button
                    type="button"
                    onClick={() => void onExcluirFoto(f.id)}
                    className="text-xs text-danger hover:underline text-left"
                  >
                    Excluir
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-2xl bg-background-surface border border-border p-5 space-y-3">
        <h2 className="text-sm font-semibold text-slate-100">Datas</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Campo label="Calibração" valor={formatData(os.data_calibracao)} />
          <Campo label="Aceite" valor={formatData(os.data_aceite)} />
          <Campo label="Retorno (postagem)" valor={formatData(os.data_retorno)} />
          <Campo label="Próxima calibração" valor={formatData(os.prox_calibragem)} />
        </div>
      </section>

      <section className="rounded-2xl bg-background-surface border border-border p-5 space-y-3">
        <h2 className="text-sm font-semibold text-slate-100">Resultados da calibração</h2>
        {temCalib ? (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <Campo label="Certificado" valor={os.calib_cert} />
            <Campo label="Temperatura" valor={os.calib_temp} />
            <Campo label="Pressão" valor={os.calib_pressao} />
            <Campo label="Média dos testes" valor={os.calib_teste_media} />
            <Campo label="Situação" valor={os.calib_situacao} />
            <Campo label="PDF" valor={os.pdf_certificado
              ? <button type="button" onClick={() => void onBaixarCertificado()} className="text-primary hover:underline text-sm">Baixar certificado</button>
              : '—'} />
          </div>
        ) : (
          <p className="text-sm text-slate-500">Sem resultados de calibração ainda.</p>
        )}
        {podeCertificado && (
          <div className="pt-1">
            <label className="cursor-pointer">
              <span className="inline-flex items-center rounded-lg px-3 py-1.5 text-xs font-medium bg-primary text-white hover:opacity-90 transition-opacity">
                Enviar certificado (PDF)
              </span>
              <input type="file" accept="application/pdf" className="hidden" onChange={onEnviarCertificado} />
            </label>
            {erroCert && <p className="text-sm text-danger mt-1">{erroCert}</p>}
          </div>
        )}
      </section>

      <section className="rounded-2xl bg-background-surface border border-border p-5 space-y-3">
        <h2 className="text-sm font-semibold text-slate-100">Histórico</h2>
        {logs.length === 0 ? (
          <p className="text-sm text-slate-500">Sem eventos.</p>
        ) : (
          <ol className="space-y-2">
            {logs.map((l) => (
              <li key={l.id} className="flex gap-3 text-sm">
                <span className="text-xs text-slate-500 shrink-0 w-28">{formatData(l.datalog)}</span>
                <span className="text-slate-200">{l.texto ?? '—'}</span>
              </li>
            ))}
          </ol>
        )}
      </section>

      {acao === 'avancar' && transicao && (
        <AvancarModal os={os} rotulo={transicao.rotulo} pedeCodRetorno={transicao.pedeCodRetorno} pedeCalibracao={transicao.pedeCalibracao} onClose={() => setAcao(null)} onConcluido={aoConcluir} />
      )}
      {acao === 'cancelar' && <CancelarModal os={os} onClose={() => setAcao(null)} onConcluido={aoConcluir} />}
    </div>
  )
}
