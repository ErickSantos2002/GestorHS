import { useEffect, useState } from 'react'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { useAuth } from '../../auth/AuthContext'
import { podeFaturarProposta, podeDesfaturarProposta } from '../../auth/roles'
import { ApiError } from '../../lib/api'
import { formatData } from '../../lib/utils'
import { formatarDocumento } from '../../lib/documento'
import { formatarMoeda } from '../../lib/moeda'
import { propostasApi, type Proposta } from '../propostas/api'
import { VisualizarPropostaModal } from '../propostas/VisualizarPropostaModal'
import { caixasApi } from './api'

/** Bloco da proposta comercial no aside da caixa — para o Financeiro conferir e
 *  faturar sem sair da tela da OS.
 *
 *  A caixa guarda so o NUMERO da proposta (gravado pelo GrowthHS ao marcar "Ganho");
 *  quem resolve numero -> Proposta e o backend. Numero que so existe no CRM antigo
 *  responde 404 e o bloco simplesmente nao aparece — como se a caixa nao tivesse
 *  proposta, que e o que ela tem aqui dentro.
 *
 *  Aparece em QUALQUER fase que tenha numero, nao so no Financeiro: a maioria das
 *  caixas com proposta ja passou da fase 10 e o faturamento pode vir depois.
 *
 *  Proposta DESABILITADA continua aparecendo, marcada e sem acao de faturar — o
 *  Financeiro precisa ver que a proposta daquela caixa saiu de circulacao. */
export function PropostaCaixaCard({ caixaId, numeroProposta }: {
  caixaId: number
  numeroProposta?: number | null
}) {
  const { user } = useAuth()
  const [proposta, setProposta] = useState<Proposta | null>(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState('')
  const [ocupado, setOcupado] = useState(false)
  const [visualizar, setVisualizar] = useState(false)

  useEffect(() => {
    if (numeroProposta == null) return
    let cancelado = false
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCarregando(true)
    caixasApi.proposta(caixaId)
      .then((p) => { if (!cancelado) setProposta(p) })
      // Sem proposta local nao ha bloco: o erro nao vira aviso na tela.
      .catch(() => { if (!cancelado) setProposta(null) })
      .finally(() => { if (!cancelado) setCarregando(false) })
    return () => { cancelado = true }
  }, [caixaId, numeroProposta])

  async function acao(fn: () => Promise<Proposta>, falha: string) {
    setErro('')
    setOcupado(true)
    try {
      setProposta(await fn())
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : falha)
    } finally {
      setOcupado(false)
    }
  }

  async function baixar() {
    if (!proposta) return
    setErro('')
    setOcupado(true)
    try {
      const blob = await propostasApi.baixarPdf(proposta.id)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `proposta-${proposta.numero}.pdf`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao baixar PDF')
    } finally {
      setOcupado(false)
    }
  }

  if (numeroProposta == null) return null
  if (carregando) {
    return (
      <section className="rounded-2xl bg-background-surface border border-border p-5 flex justify-center">
        <Spinner className="w-5 h-5" />
      </section>
    )
  }
  if (!proposta) return null

  return (
    <section className="rounded-2xl bg-background-surface border border-border p-5">
      <div className="flex items-center justify-between gap-2 mb-3">
        <p className="text-sm font-semibold text-slate-100">Proposta #{proposta.numero}</p>
        {proposta.is_deleted
          ? <Badge tone="danger">Desabilitada</Badge>
          : proposta.faturada && <Badge tone="primary">Faturada</Badge>}
      </div>

      <dl className="space-y-1 text-sm text-slate-300">
        <div className="flex justify-between gap-3">
          <dt>Data</dt><dd className="text-slate-100">{formatData(proposta.data)}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt>Cliente</dt>
          <dd className="text-slate-100 text-right">{proposta.cliente_nome ?? '—'}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt>CNPJ</dt>
          <dd className="text-slate-100">{formatarDocumento(proposta.cliente_documento) || '—'}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt>Valor</dt>
          <dd className="text-slate-100 font-semibold">R$ {formatarMoeda(proposta.total)}</dd>
        </div>
      </dl>

      {proposta.faturada && proposta.faturada_por && (
        <p className="mt-3 text-xs text-slate-500">
          Faturada em {formatData(proposta.faturada_em)} por {proposta.faturada_por}
        </p>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        <Button variant="secondary" className="px-3 py-1.5" onClick={() => setVisualizar(true)}>
          Visualizar
        </Button>
        <Button variant="secondary" className="px-3 py-1.5" disabled={ocupado} onClick={baixar}>
          Baixar
        </Button>
        {!proposta.is_deleted && !proposta.faturada && podeFaturarProposta(user) && (
          <Button
            className="px-3 py-1.5"
            disabled={ocupado}
            onClick={() => acao(() => propostasApi.faturar(proposta.id), 'Falha ao marcar como faturada')}
          >
            Marcar como faturada
          </Button>
        )}
        {!proposta.is_deleted && proposta.faturada && podeDesfaturarProposta(user) && (
          <Button
            variant="ghost"
            className="px-3 py-1.5"
            disabled={ocupado}
            onClick={() => acao(() => propostasApi.desfaturar(proposta.id), 'Falha ao desfazer o faturamento')}
          >
            Desfazer faturamento
          </Button>
        )}
      </div>

      {erro && <p className="mt-2 text-sm text-danger">{erro}</p>}

      {visualizar && (
        <VisualizarPropostaModal
          propostaId={proposta.id}
          propostaNumero={proposta.numero}
          onClose={() => setVisualizar(false)}
        />
      )}
    </section>
  )
}
