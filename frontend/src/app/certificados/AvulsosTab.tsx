import { useEffect, useState } from 'react'
import { certificadosApi, type AvulsoItem } from './api'
import { formatData } from '../../lib/utils'
import { Spinner } from '../../components/ui/Spinner'
import { Button } from '../../components/ui/Button'
import { Table, TH, TD } from '../../components/ui/Table'
import { useAuth } from '../../auth/AuthContext'
import { isAdmin } from '../../auth/roles'
import { CertificadoAvulsoModal } from './CertificadoAvulsoModal'

export function AvulsosTab() {
  const { user } = useAuth()
  const podeGerar = isAdmin(user) || user?.funcao === 'Laboratório'
  const [itens, setItens] = useState<AvulsoItem[] | null>(null)
  const [modalAberto, setModalAberto] = useState(false)

  function recarregar() {
    certificadosApi.listarAvulsos().then(setItens).catch(() => setItens([]))
  }

  useEffect(() => {
    recarregar()
  }, [])

  function onGerado() {
    setModalAberto(false)
    recarregar()
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-slate-500">Certificados emitidos sem OS — para aparelhos de POC, de empresas não cadastradas.</p>
        {podeGerar && <Button onClick={() => setModalAberto(true)} className="shrink-0">Gerar certificado em branco</Button>}
      </div>
      {itens === null ? (
        <div className="py-10 flex justify-center"><Spinner className="w-7 h-7" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum certificado avulso emitido.</p>
      ) : (
        <Table head={<><TH>Nº do certificado</TH><TH>Cliente</TH><TH>Série</TH><TH>Tipo</TH><TH>Data da calibração</TH><TH>Gerado por</TH><TH>Ações</TH></>}>
          {itens.map((a) => (
            <tr key={a.id}>
              <TD>{a.calib_cert ?? '—'}</TD>
              <TD>{a.nomecli ?? '—'}</TD>
              <TD>{a.serie ?? '—'}</TD>
              <TD>{a.tipo === 'C' ? 'Calibração' : 'Manutenção'}</TD>
              <TD>{formatData(a.data_calibracao)}</TD>
              <TD>{a.usuario_nome ?? '—'}</TD>
              <TD><button onClick={() => certificadosApi.baixarAvulsoPdf(a.id)} className="text-xs text-primary hover:underline">Baixar PDF</button></TD>
            </tr>
          ))}
        </Table>
      )}
      {modalAberto && <CertificadoAvulsoModal onClose={() => setModalAberto(false)} onGerado={onGerado} />}
    </div>
  )
}
