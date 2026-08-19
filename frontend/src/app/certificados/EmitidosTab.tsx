import { useEffect, useState } from 'react'
import { Input } from '../../components/ui/Input'
import { BotaoExportar } from '../../components/ui/BotaoExportar'
import { clientesApi, type ClienteListItem } from '../clientes/api'

/** Relatório de certificados emitidos.
 *
 * Só exportação, sem tabela: os certificados emitidos não têm tela de lista no
 * sistema — vivem em duas tabelas separadas e aparecem picados no detalhe da OS e
 * do aparelho. Aqui o usuário escolhe o recorte e leva a planilha.
 */
export function EmitidosTab() {
  const [de, setDe] = useState('')
  const [ate, setAte] = useState('')
  const [q, setQ] = useState('')
  const [resultados, setResultados] = useState<ClienteListItem[]>([])
  const [cliente, setCliente] = useState<ClienteListItem | null>(null)

  useEffect(() => {
    let vivo = true
    if (cliente || !q.trim()) {
      Promise.resolve().then(() => { if (vivo) setResultados([]) })
    } else {
      clientesApi.listar({ q: q.trim(), limit: 8 })
        .then((r) => { if (vivo) setResultados(r.items) })
        .catch(() => { if (vivo) setResultados([]) })
    }
    return () => { vivo = false }
  }, [q, cliente])

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-400 max-w-2xl">
        Gera uma planilha com todos os certificados já emitidos no período — tanto os
        que saíram de uma OS quanto os de venda. Sem período nem cliente, traz todos.
      </p>

      <div className="flex flex-wrap items-end gap-3">
        <div className="w-44">
          <Input id="de" label="De" type="date" value={de} onChange={(e) => setDe(e.target.value)} />
        </div>
        <div className="w-44">
          <Input id="ate" label="Até" type="date" value={ate} onChange={(e) => setAte(e.target.value)} />
        </div>
        <div className="w-64 relative">
          {cliente ? (
            <div className="flex items-center justify-between rounded-lg bg-primary/10 border border-primary/30 px-3 py-2">
              <span className="text-sm font-semibold text-primary">{cliente.nome ?? `#${cliente.id}`}</span>
              <button type="button" className="text-xs text-slate-400 hover:text-slate-200" onClick={() => setCliente(null)}>trocar</button>
            </div>
          ) : (
            <>
              <Input id="busca-cliente" label="Cliente" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar por nome" />
              {resultados.length > 0 && (
                <ul className="absolute z-10 mt-1 w-full rounded-lg border border-border divide-y divide-border overflow-hidden bg-background-elevated">
                  {resultados.map((c) => (
                    <li key={c.id}>
                      <button type="button" onClick={() => { setCliente(c); setQ('') }}
                        className="w-full text-left px-3 py-2 text-sm hover:bg-background-elevated">
                        {c.nome ?? `#${c.id}`}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
        <BotaoExportar
          caminho="/certificados-emitidos/exportar"
          params={{ de, ate, cliente: cliente?.id }}
          nome="certificados-emitidos"
        />
      </div>

      <p className="text-xs text-slate-500 max-w-2xl">
        A coluna "Gerado por" só existe nos certificados de venda — o sistema não
        registra o autor dos certificados gerados a partir de uma OS.
      </p>
    </div>
  )
}
