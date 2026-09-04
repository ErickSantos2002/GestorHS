import { useState, type FormEvent } from 'react'
import { Modal } from '../../components/ui/Modal'
import { Input } from '../../components/ui/Input'
import { ApiError } from '../../lib/api'
import { caixasApi, type NotaParaEnviar } from './api'

interface Props {
  caixaId: number
  onClose: () => void
  onEnviado: () => void
}

interface Bloco {
  id: number
  numero: string
  pdf: File | null
  xml: File | null
}

// Chave estavel por bloco, independente da posicao na lista. Sem isso o React
// reconcilia o `<input type="file">` pelo indice: ao remover o bloco do meio,
// o no DOM da posicao 1 e reaproveitado para o novo bloco 1, mas o `.files`
// daquele input continua sendo o arquivo do bloco antigo — a tela mostra um
// arquivo que nao pertence aquele numero de nota, mesmo com o estado (e o que
// vai pro POST) certo por baixo.
let proximoId = 0
const vazio = (): Bloco => ({ id: proximoId++, numero: '', pdf: null, xml: null })

// Anexa as notas fiscais de uma caixa. A caixa pode levar mais de uma — alem da
// nota do servico vai, as vezes, a nota de remessa do envio —, entao o modal tem
// uma lista de blocos e manda todos num POST so.
export function NotaFiscalCaixaModal({ caixaId, onClose, onEnviado }: Props) {
  const [blocos, setBlocos] = useState<Bloco[]>([vazio()])
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  function alterar(i: number, campo: Partial<Bloco>) {
    setBlocos((bs) => bs.map((b, j) => (j === i ? { ...b, ...campo } : b)))
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setErro('')
    // Validacao por bloco, dizendo QUAL: com quatro blocos na tela, "escolha o
    // XML" sozinho nao diz onde olhar. Com um bloco so (o caso comum) nao ha
    // prefixo e a frase e' a mensagem inteira — entao comeca com maiuscula, como
    // toda outra mensagem de erro do app.
    for (const [i, b] of blocos.entries()) {
      const rotulo = blocos.length > 1 ? `Nota ${i + 1}: ` : ''
      const msg = (frase: string) =>
        rotulo ? `${rotulo}${frase}` : frase.charAt(0).toUpperCase() + frase.slice(1)
      if (!b.numero.trim()) { setErro(msg('informe o número da nota fiscal.')); return }
      if (!b.pdf) { setErro(msg('escolha o PDF da nota.')); return }
      if (!b.xml) { setErro(msg('escolha o XML da nota.')); return }
    }
    const notas: NotaParaEnviar[] = blocos.map((b) => ({
      numero: b.numero.trim(), pdf: b.pdf as File, xml: b.xml as File,
    }))
    setEnviando(true)
    try {
      await caixasApi.enviarNotasFiscaisCaixa(caixaId, notas)
      onEnviado()
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Falha ao anexar a nota fiscal')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Anexar nota fiscal da caixa"
      footer={
        <>
          <button type="button" onClick={onClose} className="flex-1 py-2.5 rounded-lg border border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors">
            Cancelar
          </button>
          <button type="submit" form="form-nota-fiscal-caixa" disabled={enviando} className="flex-1 py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-50 transition-all">
            Anexar
          </button>
        </>
      }
    >
      <form id="form-nota-fiscal-caixa" className="space-y-4" onSubmit={onSubmit}>
        <p className="text-sm text-slate-400">
          As notas são anexadas a esta caixa de uma só vez. O PDF e o XML são obrigatórios
          em cada nota — sempre vêm juntos. Use “Adicionar nota” quando a caixa levar mais
          de uma (por exemplo, a nota de remessa do envio).
        </p>
        {blocos.map((b, i) => (
          <div key={b.id} className="space-y-3 rounded-lg border border-border p-3">
            <div className="flex items-end gap-2">
              <div className="flex-1">
                <Input
                  id={`numero-nf-caixa-${i}`}
                  label={`Número da nota fiscal ${i + 1}`}
                  value={b.numero}
                  onChange={(e) => alterar(i, { numero: e.target.value })}
                  maxLength={50}
                />
              </div>
              {i > 0 && (
                <button
                  type="button"
                  aria-label={`Remover nota ${i + 1}`}
                  onClick={() => setBlocos((bs) => bs.filter((_, j) => j !== i))}
                  className="mb-1 px-3 py-2 rounded-lg border border-border text-sm text-slate-400 hover:bg-background-elevated transition-colors"
                >
                  ✕
                </button>
              )}
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label htmlFor={`nf-caixa-pdf-${i}`} className="block text-sm font-medium text-slate-300 mb-1.5">
                  PDF da nota {i + 1}
                </label>
                <input
                  id={`nf-caixa-pdf-${i}`}
                  type="file"
                  accept="application/pdf,.pdf"
                  onChange={(e) => alterar(i, { pdf: e.target.files?.[0] ?? null })}
                  className="block w-full text-sm text-slate-300 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:bg-background-elevated file:text-slate-200 file:text-sm"
                />
              </div>
              <div>
                <label htmlFor={`nf-caixa-xml-${i}`} className="block text-sm font-medium text-slate-300 mb-1.5">
                  XML da nota {i + 1}
                </label>
                <input
                  id={`nf-caixa-xml-${i}`}
                  type="file"
                  accept="application/xml,text/xml,.xml"
                  onChange={(e) => alterar(i, { xml: e.target.files?.[0] ?? null })}
                  className="block w-full text-sm text-slate-300 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:bg-background-elevated file:text-slate-200 file:text-sm"
                />
              </div>
            </div>
          </div>
        ))}
        <button
          type="button"
          onClick={() => setBlocos((bs) => [...bs, vazio()])}
          className="w-full py-2 rounded-lg border border-dashed border-border text-sm font-medium text-slate-400 hover:bg-background-elevated transition-colors"
        >
          + Adicionar nota
        </button>
        {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}
      </form>
    </Modal>
  )
}
