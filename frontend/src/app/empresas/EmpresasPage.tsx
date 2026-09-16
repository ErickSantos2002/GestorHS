import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Table, TH, TD } from '../../components/ui/Table'
import { Button } from '../../components/ui/Button'
import { Badge } from '../../components/ui/Badge'
import { Spinner } from '../../components/ui/Spinner'
import { SearchBar } from '../../components/ui/SearchBar'
import { PaginationOffset } from '../../components/ui/Pagination'
import { PageContainer } from '../../components/ui/Page'
import { IconButton, IconButtonGroup } from '../../components/ui/IconButton'
import { IconBan, IconPencil, IconRestore } from '../../components/ui/icons'
import { ApiError } from '../../lib/api'
import { formatarDocumento } from '../../lib/documento'
import { useAuth } from '../../auth/AuthContext'
import { podeGerenciarEmpresas } from '../../auth/roles'
import { empresasApi, type Empresa } from './api'
import { EmpresaModal } from './EmpresaModal'

const LIMITE = 25

export function EmpresasPage() {
  const { user } = useAuth()
  const podeEditar = podeGerenciarEmpresas(user)
  const [termo, setTermo] = useState('')
  const [busca, setBusca] = useState('')
  const [offset, setOffset] = useState(0)
  const [itens, setItens] = useState<Empresa[] | null>(null)
  const [total, setTotal] = useState(0)
  const [erro, setErro] = useState('')
  const [recarga, setRecarga] = useState(0)
  const [modal, setModal] = useState<{ empresa: Empresa | null } | null>(null)

  useEffect(() => {
    let vivo = true
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setItens(null)
    setErro('')
    empresasApi.listar({ q: busca || undefined, offset, limit: LIMITE })
      .then((p) => { if (vivo) { setItens(p.items); setTotal(p.total) } })
      .catch((e) => { if (vivo) { setErro(e instanceof ApiError ? e.message : 'Falha ao carregar'); setItens([]) } })
    return () => { vivo = false }
  }, [busca, offset, recarga])

  function onBuscar(e: FormEvent) {
    e.preventDefault()
    setOffset(0)
    setBusca(termo.trim())
  }

  async function alternarAtivo(emp: Empresa) {
    try {
      await (emp.ativo ? empresasApi.desativar(emp.id) : empresasApi.reativar(emp.id))
      setRecarga((n) => n + 1)
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Falha ao alterar a empresa')
    }
  }

  return (
    <PageContainer>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold text-slate-100">Empresas</h1>
        {podeEditar && <Button onClick={() => setModal({ empresa: null })}>Nova empresa</Button>}
      </div>
      <p className="text-sm text-slate-500">Filiais com os dados cadastrais. Os aparelhos das propostas vêm do cliente matriz.</p>
      <SearchBar value={termo} onChange={setTermo} onSubmit={onBuscar} placeholder="Buscar por nome, CNPJ, CPF ou município" />
      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      {itens === null ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhuma empresa encontrada.</p>
      ) : (
        <Table
          head={<><TH>Nome</TH><TH>CNPJ / CPF</TH><TH>Matriz</TH><TH>Município/UF</TH><TH>Ativo</TH><TH>Ações</TH></>}
          footer={<PaginationOffset offset={offset} limit={LIMITE} total={total} onOffsetChange={setOffset} itemLabel="empresas" />}
        >
          {itens.map((emp) => (
            <tr key={emp.id} className="hover:bg-background-elevated transition-colors">
              <TD>{emp.nome}</TD>
              <TD>{formatarDocumento(emp.cgc || emp.cpf) || '—'}</TD>
              <TD>
                {emp.cliente != null
                  ? <Link to={`/app/clientes/${emp.cliente}`} className="text-primary hover:underline">{emp.matriz_nome ?? `Cliente #${emp.cliente}`}</Link>
                  : '—'}
              </TD>
              <TD>{[emp.municipio, emp.estado].filter(Boolean).join(' / ') || '—'}</TD>
              <TD><Badge tone={emp.ativo ? 'primary' : 'neutral'}>{emp.ativo ? 'Ativa' : 'Inativa'}</Badge></TD>
              <TD>
                <IconButtonGroup>
                  <IconButton label={podeEditar ? 'Editar' : 'Ver'} tone={podeEditar ? 'editar' : 'ver'} onClick={() => setModal({ empresa: emp })}>
                    <IconPencil className="w-4 h-4" />
                  </IconButton>
                  {podeEditar && (
                    <IconButton label={emp.ativo ? 'Desativar' : 'Reativar'} tone={emp.ativo ? 'excluir' : 'ok'} onClick={() => void alternarAtivo(emp)}>
                      {emp.ativo ? <IconBan className="w-4 h-4" /> : <IconRestore className="w-4 h-4" />}
                    </IconButton>
                  )}
                </IconButtonGroup>
              </TD>
            </tr>
          ))}
        </Table>
      )}
      {modal && (
        <EmpresaModal empresa={modal.empresa} onClose={() => setModal(null)}
          onSalvo={() => { setModal(null); setRecarga((n) => n + 1) }} />
      )}
    </PageContainer>
  )
}
