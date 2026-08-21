import { useEffect, useState, type FormEvent } from 'react'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { Spinner } from '../../components/ui/Spinner'
import { IconButton, IconButtonGroup } from '../../components/ui/IconButton'
import { IconPencil, IconTrash } from '../../components/ui/icons'
import { useAuth } from '../../auth/AuthContext'
import { podeEditarConfigCertificado, podeExcluirCilindro } from '../../auth/roles'
import { mensagemDeErro } from './erros'
import { manutencaoApi, type ServicoManutencao } from '../ordens/manutencao'

/** Catálogo fechado dos serviços que o Relatório de Manutenção aceita.
 *
 * Fica aqui, e não em Cadastros: aquela página inteira é fechada para
 * Administrador, e o Laboratório precisa cadastrar serviço. Mesmo público da
 * aba Configurações — por isso reaproveita `podeEditarConfigCertificado`. */
export function ServicosManutencaoTab() {
  const { user } = useAuth()
  const podeEditar = podeEditarConfigCertificado(user)
  const podeExcluir = podeExcluirCilindro(user)

  const [itens, setItens] = useState<ServicoManutencao[] | null>(null)
  const [erro, setErro] = useState('')
  const [aberto, setAberto] = useState(false)
  const [editando, setEditando] = useState<ServicoManutencao | null>(null)
  const [descricao, setDescricao] = useState('')
  const [resumoPadrao, setResumoPadrao] = useState('')
  const [ativo, setAtivo] = useState(true)
  const [erroForm, setErroForm] = useState('')
  const [salvando, setSalvando] = useState(false)

  function carregar() {
    setErro('')
    void manutencaoApi.listarServicos()
      .then(setItens)
      .catch((e) => { setErro(mensagemDeErro(e, 'Falha ao carregar')); setItens([]) })
  }

  // Efeito de carga inicial separado de `carregar` (reaproveitada após criar/editar/excluir,
  // sempre a partir de um handler de evento): chamar `carregar` direto no useEffect dispara
  // o setErro('') síncrono no corpo do efeito, que o react-hooks/set-state-in-effect recusa.
  useEffect(() => {
    let vivo = true
    manutencaoApi.listarServicos()
      .then((r) => { if (vivo) setItens(r) })
      .catch((e) => { if (vivo) { setErro(mensagemDeErro(e, 'Falha ao carregar')); setItens([]) } })
    return () => { vivo = false }
  }, [])

  function abrirNovo() {
    setEditando(null); setDescricao(''); setResumoPadrao(''); setAtivo(true)
    setErroForm(''); setAberto(true)
  }

  function abrirEdicao(s: ServicoManutencao) {
    setEditando(s); setDescricao(s.descricao); setResumoPadrao(s.resumo_padrao); setAtivo(s.ativo)
    setErroForm(''); setAberto(true)
  }

  async function submeter(e: FormEvent) {
    e.preventDefault()
    if (!descricao.trim()) { setErroForm('Informe a descrição.'); return }
    setErroForm(''); setSalvando(true)
    try {
      if (editando) {
        await manutencaoApi.atualizarServico(editando.id, {
          descricao: descricao.trim(), resumo_padrao: resumoPadrao.trim(), ativo,
        })
      } else {
        await manutencaoApi.criarServico({ descricao: descricao.trim(), resumo_padrao: resumoPadrao.trim() })
      }
      setAberto(false)
      carregar()
    } catch (err) {
      setErroForm(mensagemDeErro(err, 'Falha ao salvar o serviço'))
    } finally {
      setSalvando(false)
    }
  }

  async function excluir(s: ServicoManutencao) {
    if (!window.confirm(`Excluir o serviço "${s.descricao}"?\n\nSe ele já foi usado em algum relatório, desative em vez de excluir.`)) return
    try {
      await manutencaoApi.excluirServico(s.id)
      carregar()
    } catch (err) {
      setErro(mensagemDeErro(err, 'Falha ao excluir'))
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-100">Serviços de manutenção</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            O relatório de manutenção só aceita serviços desta lista. O resumo padrão é a frase que entra no "Resumo do Serviço".
          </p>
        </div>
        {podeEditar && <Button onClick={abrirNovo}>Novo serviço</Button>}
      </div>

      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}

      {itens === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum serviço cadastrado ainda.</p>
      ) : (
        <Table head={<><TH>Serviço</TH><TH>Resumo padrão</TH><TH>Situação</TH><TH> </TH></>}>
          {itens.map((s) => (
            <tr key={s.id} className="hover:bg-background-elevated transition-colors">
              <TD>{s.descricao}</TD>
              <TD><span className="text-slate-400">{s.resumo_padrao || '—'}</span></TD>
              <TD>{s.ativo ? <Badge tone="primary">Ativo</Badge> : <Badge tone="neutral">Inativo</Badge>}</TD>
              <TD>
                <IconButtonGroup>
                  {podeEditar && (
                    <IconButton label="Editar" tone="editar" onClick={() => abrirEdicao(s)}>
                      <IconPencil className="w-4 h-4" />
                    </IconButton>
                  )}
                  {podeExcluir && (
                    <IconButton label="Excluir" tone="excluir" onClick={() => void excluir(s)}>
                      <IconTrash className="w-4 h-4" />
                    </IconButton>
                  )}
                </IconButtonGroup>
              </TD>
            </tr>
          ))}
        </Table>
      )}

      {aberto && (
        <Modal
          open
          onClose={() => setAberto(false)}
          title={editando ? 'Editar serviço' : 'Novo serviço'}
          footer={
            <>
              <Button variant="secondary" type="button" onClick={() => setAberto(false)} disabled={salvando}>Cancelar</Button>
              <Button type="submit" form="form-servico-manut" disabled={salvando}>Salvar</Button>
            </>
          }
        >
          <form id="form-servico-manut" className="space-y-4" onSubmit={submeter}>
            <Input id="serv-descricao" label="Descrição" value={descricao}
                   onChange={(e) => setDescricao(e.target.value)} maxLength={200} />
            <div className="space-y-1">
              <label htmlFor="serv-resumo" className="block text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Resumo padrão
              </label>
              <textarea id="serv-resumo" rows={4} value={resumoPadrao}
                        onChange={(e) => setResumoPadrao(e.target.value)}
                        className="w-full rounded-lg bg-background border border-border px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-primary/40" />
            </div>
            {editando && (
              <label className="flex items-center gap-2 text-sm text-slate-300">
                <input type="checkbox" checked={ativo} onChange={(e) => setAtivo(e.target.checked)} />
                Ativo
              </label>
            )}
            {erroForm && <p className="text-sm text-danger">{erroForm}</p>}
          </form>
        </Modal>
      )}
    </div>
  )
}
