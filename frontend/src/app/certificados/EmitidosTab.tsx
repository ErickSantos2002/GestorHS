import { useState } from 'react'
import { Input } from '../../components/ui/Input'
import { BotaoExportar } from '../../components/ui/BotaoExportar'

/** Relatório de certificados emitidos.
 *
 * Só exportação, sem tabela: os certificados emitidos não têm tela de lista no
 * sistema — vivem em duas tabelas separadas e aparecem picados no detalhe da OS e
 * do aparelho. Aqui o usuário escolhe o recorte e leva a planilha.
 */
export function EmitidosTab() {
  const [de, setDe] = useState('')
  const [ate, setAte] = useState('')

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-400 max-w-2xl">
        Gera uma planilha com todos os certificados já emitidos no período — tanto os
        que saíram de uma OS quanto os de venda. Sem período, traz todos.
      </p>

      <div className="flex flex-wrap items-end gap-3">
        <div className="w-44">
          <Input id="de" label="De" type="date" value={de} onChange={(e) => setDe(e.target.value)} />
        </div>
        <div className="w-44">
          <Input id="ate" label="Até" type="date" value={ate} onChange={(e) => setAte(e.target.value)} />
        </div>
        <BotaoExportar
          caminho="/certificados-emitidos/exportar"
          params={{ de, ate }}
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
