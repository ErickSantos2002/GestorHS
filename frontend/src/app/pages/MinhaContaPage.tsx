import { useState, type FormEvent } from 'react'
import { Input } from '../../components/ui/Input'
import { ApiError } from '../../lib/api'
import { trocarMinhaSenha } from '../acesso/api'
import { PageContainer } from '../../components/ui/Page'

export function MinhaContaPage() {
  const [atual, setAtual] = useState('')
  const [nova, setNova] = useState('')
  const [confirma, setConfirma] = useState('')
  const [msg, setMsg] = useState<{ tipo: 'ok' | 'erro'; texto: string } | null>(null)
  const [enviando, setEnviando] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (nova !== confirma) {
      setMsg({ tipo: 'erro', texto: 'A confirmação não confere' })
      return
    }
    setEnviando(true)
    try {
      await trocarMinhaSenha(atual, nova)
      setMsg({ tipo: 'ok', texto: 'Senha alterada com sucesso' })
      setAtual('')
      setNova('')
      setConfirma('')
    } catch (err) {
      setMsg({ tipo: 'erro', texto: err instanceof ApiError ? err.message : 'Falha ao alterar' })
    } finally {
      setEnviando(false)
    }
  }

  return (
    <PageContainer>
      <h1 className="text-2xl font-extrabold text-slate-100 mb-6">Minha conta</h1>
      <div className="rounded-2xl bg-background-surface border border-border p-6 max-w-md">
        <h2 className="text-sm font-semibold text-slate-100 mb-4">Trocar senha</h2>
        <form className="space-y-4" onSubmit={onSubmit}>
          <Input id="atual" label="Senha atual" type="password" value={atual} onChange={(e) => setAtual(e.target.value)} required />
          <Input id="nova" label="Nova senha (mín. 8)" type="password" value={nova} onChange={(e) => setNova(e.target.value)} required minLength={8} />
          <Input
            id="confirma"
            label="Confirmar nova senha"
            type="password"
            value={confirma}
            onChange={(e) => setConfirma(e.target.value)}
            required
            minLength={8}
          />
          {msg && (
            <div
              className={
                msg.tipo === 'ok'
                  ? 'rounded-lg bg-primary/10 border border-primary/20 px-3 py-2.5 text-sm text-primary'
                  : 'rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger'
              }
            >
              {msg.texto}
            </div>
          )}
          <button
            type="submit"
            disabled={enviando}
            className="w-full py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-60 transition-all"
          >
            Salvar
          </button>
        </form>
      </div>
    </PageContainer>
  )
}
