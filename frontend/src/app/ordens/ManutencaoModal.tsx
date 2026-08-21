import { useEffect, useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { ApiError } from '../../lib/api'
import { comporResumo, manutencaoApi, type Manutencao, type ServicoManutencao } from './manutencao'

export function ManutencaoModal({ osId, onClose, onSalvo }: {
  osId: number
  onClose: () => void
  onSalvo: (m: Manutencao) => void
}) {
  const [servicos, setServicos] = useState<ServicoManutencao[] | null>(null)
  const [escolhidos, setEscolhidos] = useState<number[]>([])
  const [numero, setNumero] = useState('')
  const [data, setData] = useState('')
  const [resumo, setResumo] = useState('')
  // Guarda a ultima composicao automatica. Enquanto o texto for igual a ela, o
  // resumo acompanha a escolha de servicos; assim que o tecnico edita, para de
  // acompanhar — senao acrescentar um servico apagaria o texto dele.
  const [composicao, setComposicao] = useState('')
  const [erro, setErro] = useState('')
  const [salvando, setSalvando] = useState(false)

  useEffect(() => {
    let vivo = true
    void manutencaoApi.listarServicos()
      .then((lista) => { if (vivo) setServicos(lista.filter((s) => s.ativo)) })
      .catch(() => { if (vivo) setServicos([]) })
    // Manutencao ja registrada: 404 aqui e' o caso normal da primeira vez.
    void manutencaoApi.obter(osId)
      .then((m) => {
        if (!vivo) return
        setNumero(m.numero ?? '')
        setData(m.data_manutencao ?? '')
        setResumo(m.resumo ?? '')
        // A composicao que ESTES servicos gerariam — nao o texto salvo. Se o
        // salvo bate com ela, foi automatico e segue acompanhando os servicos;
        // se difere, foi editado a mao e fica congelado.
        setComposicao(comporResumo(m.servicos.map((s) => s.resumo_padrao)))
        setEscolhidos(m.servicos.map((s) => s.servico))
      })
      .catch(() => { /* sem manutencao ainda */ })
    return () => { vivo = false }
  }, [osId])

  function alternar(servico: ServicoManutencao) {
    const novos = escolhidos.includes(servico.id)
      ? escolhidos.filter((x) => x !== servico.id)
      : [...escolhidos, servico.id]
    setEscolhidos(novos)
    const frases = novos.map((id) => (servicos ?? []).find((s) => s.id === id)?.resumo_padrao ?? '')
    const nova = comporResumo(frases)
    if (resumo === composicao) {
      setResumo(nova)
    }
    setComposicao(nova)
  }

  const resumoDesacoplado = resumo !== composicao && resumo.trim() !== ''

  async function submeter(e: FormEvent) {
    e.preventDefault()
    if (escolhidos.length === 0) { setErro('Escolha ao menos um serviço.'); return }
    setErro('')
    setSalvando(true)
    try {
      const m = await manutencaoApi.salvar(osId, {
        numero: numero.trim() || null,
        data_manutencao: data || null,
        resumo: resumo.trim() || null,
        servicos: escolhidos,
      })
      onSalvo(m)
      onClose()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao salvar a manutenção')
    } finally {
      setSalvando(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Registrar manutenção"
      size="2xl"
      closeOnBackdrop={false}
      footer={
        <>
          <Button variant="secondary" type="button" onClick={onClose} disabled={salvando}>Cancelar</Button>
          <Button type="submit" form="form-manutencao" disabled={salvando}>
            {salvando ? 'Salvando…' : 'Salvar manutenção'}
          </Button>
        </>
      }
    >
      <form id="form-manutencao" className="space-y-4" onSubmit={submeter}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Input id="manut-numero" label="Número do relatório" value={numero}
                 onChange={(e) => setNumero(e.target.value)} maxLength={50} />
          <Input id="manut-data" label="Data da manutenção" type="date" value={data}
                 onChange={(e) => setData(e.target.value)} />
        </div>

        <div className="space-y-1.5">
          <span className="block text-xs font-semibold text-slate-500 uppercase tracking-wide">Serviços executados</span>
          {servicos === null ? (
            <Spinner className="w-5 h-5" />
          ) : servicos.length === 0 ? (
            <p className="text-sm text-slate-500">Nenhum serviço cadastrado — cadastre em Certificados › Serviços de manutenção.</p>
          ) : (
            <div className="space-y-1">
              {servicos.map((s) => (
                <label key={s.id} className="flex items-center gap-2 text-sm text-slate-200">
                  <input type="checkbox" aria-label={s.descricao}
                         checked={escolhidos.includes(s.id)} onChange={() => alternar(s)} />
                  {s.descricao}
                </label>
              ))}
            </div>
          )}
        </div>

        <div className="space-y-1">
          <label htmlFor="manut-resumo" className="block text-xs font-semibold text-slate-500 uppercase tracking-wide">
            Resumo do serviço
          </label>
          <textarea id="manut-resumo" rows={6} value={resumo}
                    onChange={(e) => setResumo(e.target.value)}
                    className="w-full rounded-lg bg-background border border-border px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-primary/40" />
          {resumoDesacoplado && (
            <p className="text-xs text-slate-500">
              Você editou este texto — ele não acompanha mais os serviços escolhidos.
            </p>
          )}
        </div>

        {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      </form>
    </Modal>
  )
}
