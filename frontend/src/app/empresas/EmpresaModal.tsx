import { useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { ApiError } from '../../lib/api'
import { useAuth } from '../../auth/AuthContext'
import { podeGerenciarEmpresas } from '../../auth/roles'
import { empresasApi, rotuloTiny, type Empresa } from './api'
import { camposFaltando, dadosDeEmpresa, dadosVazios, type DadosEmpresa } from './dadosEmpresa'
import { DadosEmpresaForm } from './DadosEmpresaForm'
import { MatrizSelect, type MatrizValor } from './MatrizSelect'
import { montarPayloadEmpresa } from './utils'

const OBRIGATORIOS = ['nome', 'documento'] as const

export function EmpresaModal({ empresa, onClose, onSalvo }: {
  empresa: Empresa | null
  onClose: () => void
  onSalvo: (e: Empresa) => void
}) {
  const { user } = useAuth()
  const podeEditar = podeGerenciarEmpresas(user)
  const [dados, setDados] = useState<DadosEmpresa>(() => (empresa ? dadosDeEmpresa(empresa, { comContato: true }) : dadosVazios()))
  const [matriz, setMatriz] = useState<MatrizValor | null>(
    empresa?.cliente != null ? { id: empresa.cliente, nome: empresa.matriz_nome } : null,
  )
  const [inscEst, setInscEst] = useState(empresa?.insc_est ?? '')
  const [tentou, setTentou] = useState(false)
  const [erro, setErro] = useState('')
  const [salvando, setSalvando] = useState(false)

  async function salvar(e: FormEvent) {
    e.preventDefault()
    setTentou(true)
    if (camposFaltando(dados, OBRIGATORIOS).length) {
      setErro('Preencha razão social e CNPJ/CPF.')
      return
    }
    setErro('')
    setSalvando(true)
    try {
      const payload = montarPayloadEmpresa(dados, matriz, inscEst)
      const salva = empresa ? await empresasApi.atualizar(empresa.id, payload) : await empresasApi.criar(payload)
      onSalvo(salva)
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao salvar a empresa')
    } finally {
      setSalvando(false)
    }
  }

  return (
    <Modal open onClose={onClose} title={empresa ? `Empresa: ${empresa.nome}` : 'Nova empresa'} size="3xl" closeOnBackdrop={false}
      footer={
        <>
          <Button variant="secondary" type="button" onClick={onClose} disabled={salvando}>{podeEditar ? 'Cancelar' : 'Fechar'}</Button>
          {podeEditar && <Button type="submit" form="form-empresa" disabled={salvando}>{salvando ? 'Salvando…' : 'Salvar'}</Button>}
        </>
      }
    >
      <form id="form-empresa" onSubmit={salvar} className="space-y-4">
        {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
        <DadosEmpresaForm dados={dados} onChange={setDados} somenteLeitura={!podeEditar}
          obrigatorios={OBRIGATORIOS} destacarFaltando={tentou} idPrefixo="emp">
          <Input id="emp-insc-est" label="Inscrição estadual" value={inscEst} disabled={!podeEditar}
            onChange={(e) => setInscEst(e.target.value)} />
          <MatrizSelect valor={matriz} onChange={setMatriz} disabled={!podeEditar} />
        </DadosEmpresaForm>
        {empresa && (
          <p className="text-xs text-slate-500">
            Tiny: {rotuloTiny(empresa)}
            {empresa.tiny_id != null && ` · contato ${empresa.tiny_id}`}
            {empresa.tiny_erro && ` · ${empresa.tiny_erro}`}
          </p>
        )}
      </form>
    </Modal>
  )
}
