import { useEffect, useState } from 'react'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { isAdmin } from '../../auth/roles'
import { listarUsuarios, listarFuncoes, desativarUsuario, reativarUsuario, type UsuarioItem, type Funcao } from './api'
import { UsuarioFormModal } from './UsuarioFormModal'
import { RedefinirSenhaModal } from './RedefinirSenhaModal'
import { PageContainer } from '../../components/ui/Page'
import { Toggle } from '../../components/ui/Toggle'

export function UsuariosPage() {
  const { user } = useAuth()
  const [usuarios, setUsuarios] = useState<UsuarioItem[] | null>(null)
  const [funcoes, setFuncoes] = useState<Funcao[]>([])
  const [erro, setErro] = useState('')
  const [formAberto, setFormAberto] = useState(false)
  const [editando, setEditando] = useState<UsuarioItem | null>(null)
  const [senhaDe, setSenhaDe] = useState<UsuarioItem | null>(null)
  const [mostrarInativos, setMostrarInativos] = useState(false)

  async function carregar() {
    setErro('')
    try {
      const [us, fs] = await Promise.all([listarUsuarios(mostrarInativos), listarFuncoes()])
      setUsuarios(us)
      setFuncoes(fs)
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao carregar')
      setUsuarios([])
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (isAdmin(user)) void carregar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, mostrarInativos])

  if (!isAdmin(user)) {
    return (
      <div className="px-4 md:px-6 py-6">
        <p className="text-sm text-slate-400">Acesso restrito a administradores.</p>
      </div>
    )
  }

  async function onDesativar(u: UsuarioItem) {
    const alvo = u.nome ?? u.email
    if (!window.confirm(`Desativar o usuário "${alvo}"?\n\nEle perde o acesso ao sistema, mas o histórico das OS é preservado.`)) return
    try {
      await desativarUsuario(u.id)
      await carregar()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao desativar')
    }
  }

  async function onReativar(u: UsuarioItem) {
    try {
      await reativarUsuario(u.id)
      await carregar()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao reativar')
    }
  }

  return (
    <PageContainer>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold text-slate-100">Usuários</h1>
        <div className="flex items-center gap-4">
          <Toggle checked={mostrarInativos} onChange={setMostrarInativos} label="Mostrar desativados" />
          <Button
            onClick={() => {
              setEditando(null)
              setFormAberto(true)
            }}
          >
            Novo usuário
          </Button>
        </div>
      </div>

      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}

      {usuarios === null ? (
        <div className="flex justify-center py-12">
          <Spinner className="w-8 h-8" />
        </div>
      ) : usuarios.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum usuário cadastrado.</p>
      ) : (
        <Table
          head={
            <>
              <TH>Nome</TH>
              <TH>E-mail</TH>
              <TH>Função</TH>
              <TH>Status</TH>
              <TH>Ações</TH>
            </>
          }
        >
          {usuarios.map((u) => (
            <tr key={u.id} className="hover:bg-background-elevated transition-colors">
              <TD>{u.nome ?? '—'}</TD>
              <TD>{u.email}</TD>
              <TD>{u.funcao ? <Badge tone={u.funcao === 'Administrador' ? 'primary' : 'neutral'}>{u.funcao}</Badge> : '—'}</TD>
              <TD>{u.ativo ? <Badge tone="primary">Ativo</Badge> : <Badge tone="warning">Desativado</Badge>}</TD>
              <TD>
                <div className="flex gap-3">
                  <button
                    onClick={() => {
                      setEditando(u)
                      setFormAberto(true)
                    }}
                    className="text-xs text-primary hover:underline"
                  >
                    Editar
                  </button>
                  <button onClick={() => setSenhaDe(u)} className="text-xs text-slate-400 hover:text-slate-200">
                    Senha
                  </button>
                  {u.ativo ? (
                    <button onClick={() => onDesativar(u)} className="text-xs text-danger hover:underline">
                      Desativar
                    </button>
                  ) : (
                    <button onClick={() => onReativar(u)} className="text-xs text-primary hover:underline">
                      Reativar
                    </button>
                  )}
                </div>
              </TD>
            </tr>
          ))}
        </Table>
      )}

      {formAberto && (
        <UsuarioFormModal
          funcoes={funcoes}
          usuario={editando}
          onClose={() => setFormAberto(false)}
          onSalvo={() => {
            setFormAberto(false)
            void carregar()
          }}
        />
      )}

      {senhaDe && (
        <RedefinirSenhaModal
          usuario={senhaDe}
          onClose={() => setSenhaDe(null)}
          onSalvo={() => {
            setSenhaDe(null)
            void carregar()
          }}
        />
      )}
    </PageContainer>
  )
}
