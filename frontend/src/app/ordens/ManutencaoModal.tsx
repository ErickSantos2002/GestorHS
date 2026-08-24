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
  // Catalogo INTEIRO (ativos e inativos). O filtro de exibicao acontece na
  // renderizacao, para nao perder de vista um servico ja escolhido que foi
  // desativado depois — ver `visiveis` abaixo.
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
  // Falha REAL ao ler a manutencao ja registrada (500, rede fora) — diferente do
  // 404, que so quer dizer "ainda nao existe". Com o modal vazio por falha, um
  // PUT substituiria numero, data, servicos e o resumo revisado a mao; por isso
  // aqui salvar fica bloqueado ate recarregar.
  const [erroCarregar, setErroCarregar] = useState('')
  const [salvando, setSalvando] = useState(false)

  useEffect(() => {
    let vivo = true
    void manutencaoApi.listarServicos()
      .then((lista) => { if (vivo) setServicos(lista) })
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
      .catch((e) => {
        if (!vivo) return
        // 404 = ainda nao ha manutencao, o caso normal da primeira vez.
        if (e instanceof ApiError && e.status === 404) return
        setErroCarregar('Não foi possível carregar a manutenção já registrada. '
          + 'Feche e abra de novo antes de salvar — salvar agora apagaria o que estiver gravado.')
      })
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

  // Inativo aparece SO se ja estiver escolhido nesta manutencao: escondê-lo
  // deixaria um serviço gravado sem checkbox — impossível de desmarcar, fora do
  // resumo composto e ainda assim impresso em "Tipo do Problema". Inativo que
  // ninguém escolheu continua fora, que é o ponto de desativar.
  const visiveis = (servicos ?? []).filter((s) => s.ativo || escolhidos.includes(s.id))

  const resumoDesacoplado = resumo !== composicao && resumo.trim() !== ''

  async function submeter(e: FormEvent) {
    e.preventDefault()
    if (erroCarregar) return
    // Numero e data sao exigidos aqui pelo mesmo motivo do 409 do backend: sem
    // eles o relatorio sai com "N°" e "Data da Manutenção" em branco.
    if (!numero.trim()) { setErro('Informe o número do relatório.'); return }
    if (!data) { setErro('Informe a data da manutenção.'); return }
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
          <Button type="submit" form="form-manutencao" disabled={salvando || erroCarregar !== ''}>
            {salvando ? 'Salvando…' : 'Salvar manutenção'}
          </Button>
        </>
      }
    >
      <form id="form-manutencao" className="space-y-4" onSubmit={submeter}>
        {erroCarregar && (
          <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erroCarregar}</div>
        )}
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
          ) : visiveis.length === 0 ? (
            <p className="text-sm text-slate-500">Nenhum serviço cadastrado — cadastre em Certificados › Serviços de manutenção.</p>
          ) : (
            <div className="space-y-1">
              {visiveis.map((s) => (
                <label key={s.id} className="flex items-center gap-2 text-sm text-slate-200">
                  <input type="checkbox" aria-label={s.descricao}
                         checked={escolhidos.includes(s.id)} onChange={() => alternar(s)} />
                  {s.descricao}
                  {!s.ativo && (
                    <span className="text-xs text-warning">(serviço desativado — desmarque para tirar do relatório)</span>
                  )}
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
