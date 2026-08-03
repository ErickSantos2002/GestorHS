import { useEffect, useState } from 'react'
import QRCode from 'qrcode'
import { certificadosApi, type CertGeralItem } from './api'
import { Spinner } from '../../components/ui/Spinner'
import { useAuth } from '../../auth/AuthContext'
import { podeGerenciarCertificadosGerais } from '../../auth/roles'
import { ApiError } from '../../lib/api'
import { mensagemDeErro } from './erros'

export function CertificadosGeraisTab() {
  const { user } = useAuth()
  const podeEditar = podeGerenciarCertificadosGerais(user)
  const [itens, setItens] = useState<CertGeralItem[] | null>(null)
  const [nome, setNome] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [copiado, setCopiado] = useState<number | null>(null)
  const [qr, setQr] = useState<{ id: number; url: string } | null>(null)

  function recarregar() {
    certificadosApi.listarGerais().then(setItens).catch(() => setItens([]))
  }
  useEffect(recarregar, [])

  async function onEnviar(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    if (!nome.trim()) { setErro('Dê um nome antes de anexar o arquivo'); e.target.value = ''; return }
    setEnviando(true); setErro('')
    try { await certificadosApi.enviarGeral(nome.trim(), file); setNome(''); recarregar() }
    catch (err) { setErro(err instanceof ApiError ? err.message : 'Falha ao anexar') }
    finally { setEnviando(false); e.target.value = '' }
  }

  async function copiar(item: CertGeralItem) {
    if (!item.link) return
    try { await navigator.clipboard.writeText(item.link); setCopiado(item.id); setTimeout(() => setCopiado(null), 1500) } catch { /* ignore */ }
  }

  async function mostrarQr(item: CertGeralItem) {
    if (!item.link) return
    if (qr?.id === item.id) { setQr(null); return }
    const url = await QRCode.toDataURL(item.link, { width: 240, margin: 1 })
    setQr({ id: item.id, url })
  }

  async function onExcluir(id: number) {
    if (!window.confirm('Excluir este certificado?')) return
    try { await certificadosApi.excluirGeral(id); recarregar() }
    catch (err) { setErro(mensagemDeErro(err, 'Falha ao excluir')) }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-500">
        Certificados gerais (ex.: certificado de gás anual). Anexe o PDF, dê um nome e compartilhe o link/QR com o cliente — sem precisar de login.
      </p>

      {podeEditar && (
        <div className="flex flex-wrap items-end gap-3 rounded-2xl bg-background-surface border border-border p-4">
          <div className="flex-1 min-w-60">
            <label className="block text-xs font-medium text-slate-400 mb-1">Nome</label>
            <input value={nome} onChange={(e) => setNome(e.target.value)} placeholder="Ex.: Certificado de Gás 2027"
              className="w-full text-sm text-slate-200 bg-background-elevated border border-border rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-primary/40 placeholder-slate-500" />
          </div>
          <label className="cursor-pointer shrink-0">
            <span className="inline-flex items-center rounded-lg px-3 py-2.5 text-sm font-semibold bg-primary text-white hover:bg-primary-600 transition-colors">
              {enviando ? 'Enviando…' : 'Anexar PDF'}
            </span>
            <input type="file" accept="application/pdf" className="hidden" onChange={onEnviar} disabled={enviando} />
          </label>
        </div>
      )}

      {erro && <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2.5 text-sm text-danger">{erro}</div>}

      {itens === null ? (
        <div className="py-10 flex justify-center"><Spinner className="w-7 h-7" /></div>
      ) : itens.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum certificado geral anexado.</p>
      ) : (
        <ul className="space-y-2">
          {itens.map((item) => (
            <li key={item.id} className="rounded-2xl bg-background-surface border border-border p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-slate-100">{item.nome}</p>
                  <p className="text-xs text-slate-500">
                    {item.data_upload ? new Date(item.data_upload).toLocaleDateString('pt-BR') : '—'}
                    {item.usuario_nome ? ` · ${item.usuario_nome}` : ''}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {item.link ? (
                    <>
                      <button onClick={() => copiar(item)} className="text-xs font-semibold text-primary hover:underline">
                        {copiado === item.id ? 'Copiado!' : 'Copiar link'}
                      </button>
                      <button onClick={() => mostrarQr(item)} className="text-xs font-semibold text-primary hover:underline">
                        {qr?.id === item.id ? 'Ocultar QR' : 'QR code'}
                      </button>
                    </>
                  ) : (
                    <span className="text-xs text-slate-500">link público indisponível</span>
                  )}
                  {podeEditar && (
                    <button onClick={() => onExcluir(item.id)} className="text-xs font-semibold text-danger hover:underline">Excluir</button>
                  )}
                </div>
              </div>
              {qr?.id === item.id && (
                <div className="mt-3 flex flex-col items-center gap-2">
                  <img src={qr.url} alt={`QR de ${item.nome}`} className="rounded-lg bg-white p-2" width={200} height={200} />
                  <a href={qr.url} download={`qr-${item.nome}.png`} className="text-xs font-semibold text-primary hover:underline">Baixar QR</a>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
