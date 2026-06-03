import { useEffect, useState, type ReactNode } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { ApiError } from '../../lib/api'
import { ordensApi, TIPO_SERVICO, formatData, type OrdemDetalhe, type LogOS } from './api'

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
  const osId = Number(id)
  const [os, setOs] = useState<OrdemDetalhe | null>(null)
  const [logs, setLogs] = useState<LogOS[]>([])
  const [erro, setErro] = useState('')
  const [carregando, setCarregando] = useState(true)

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
        <Button variant="secondary" onClick={() => navigate('/app/ordens')}>Voltar</Button>
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
          <Campo label="Acessórios" valor={os.acessorios} />
          <Campo label="Data de chegada" valor={formatData(os.data_chegada)} />
        </div>
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
            <Campo label="PDF" valor={os.pdf_certificado} />
          </div>
        ) : (
          <p className="text-sm text-slate-500">Sem resultados de calibração ainda.</p>
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
    </div>
  )
}
