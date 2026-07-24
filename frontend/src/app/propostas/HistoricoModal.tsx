import { useEffect, useState } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { ApiError } from '../../lib/api'
import { propostasApi, type PropostaVersao } from './api'
import { coerceSnapshot, diffSnapshots } from './historico'

const formatarMoeda = (v: number) => v.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

function formatarDataHora(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return isNaN(d.getTime()) ? '—' : d.toLocaleString('pt-BR')
}

export function HistoricoModal({ propostaId, propostaNumero, onClose }: {
  propostaId: number
  propostaNumero?: number | null
  onClose: () => void
}) {
  const [versoes, setVersoes] = useState<PropostaVersao[] | null>(null)
  const [erro, setErro] = useState('')
  const [ocupada, setOcupada] = useState<number | null>(null)

  useEffect(() => {
    let vivo = true
    propostasApi
      .listarVersoes(propostaId)
      .then((r) => { if (vivo) setVersoes(r) })
      .catch((e) => { if (vivo) { setErro(e instanceof ApiError ? e.message : 'Falha ao carregar histórico'); setVersoes([]) } })
    return () => { vivo = false }
  }, [propostaId])

  async function baixarPdf(versaoId: number, numeroVersao: number) {
    setErro('')
    setOcupada(versaoId)
    try {
      const blob = await propostasApi.baixarVersaoPdf(propostaId, versaoId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `proposta-${propostaNumero ?? propostaId}-v${numeroVersao}.pdf`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao baixar PDF')
    } finally {
      setOcupada(null)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={`Histórico da proposta${propostaNumero != null ? ` #${propostaNumero}` : ''}`}
      size="xl"
      footer={<Button variant="secondary" onClick={onClose}>Fechar</Button>}
    >
      {erro && (
        <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger mb-3">{erro}</div>
      )}

      {versoes === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : versoes.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhuma versão registrada.</p>
      ) : (
        <ul className="space-y-3">
          {versoes.map((v, i) => {
            const snap = coerceSnapshot(v.snapshot)
            // A lista vem desc por numero_versao — a versão anterior é a próxima da lista.
            const anterior = coerceSnapshot(versoes[i + 1]?.snapshot ?? null)
            const diff = snap && anterior ? diffSnapshots(anterior, snap) : []
            const primeira = !anterior
            return (
              <li key={v.id} className="rounded-lg border border-border bg-background-elevated p-3.5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <span className="font-semibold text-slate-100">#v{v.numero_versao}</span>
                    <span className="ml-2 text-xs text-slate-500">{formatarDataHora(v.created_at)}</span>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Alterado por {v.alterado_por ?? '—'}
                      {snap && <span className="ml-2 text-slate-300">Total R$ {formatarMoeda(snap.total)}</span>}
                    </p>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <Button
                      variant="secondary"
                      className="px-2.5 py-1 text-xs"
                      disabled={!v.has_pdf || ocupada === v.id}
                      onClick={() => baixarPdf(v.id, v.numero_versao)}
                    >
                      PDF
                    </Button>
                  </div>
                </div>

                <div className="mt-2.5 border-t border-border pt-2.5">
                  {primeira ? (
                    <p className="text-xs text-slate-500">Versão inicial.</p>
                  ) : diff.length === 0 ? (
                    <p className="text-xs text-slate-500">Sem alterações de valores em relação à versão anterior.</p>
                  ) : (
                    <ul className="space-y-1">
                      {diff.map((linha, j) => (
                        <li key={j} className="text-xs text-slate-300 flex gap-1.5">
                          <span className="text-primary">•</span>
                          <span>{linha}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </Modal>
  )
}
