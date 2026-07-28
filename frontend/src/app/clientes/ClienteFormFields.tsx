import type { FormEvent, ReactNode } from 'react'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { mascararCNPJ, mascararCPF, soDigitos } from '../../lib/documento'
import type { ClientePayload } from './api'
import type { Grupo } from '../cadastros/api'

function Secao({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <div className="rounded-2xl bg-background-surface border border-border p-5 space-y-4">
      <h2 className="text-sm font-semibold text-slate-100">{titulo}</h2>
      {children}
    </div>
  )
}

interface ClienteFormFieldsProps {
  form: ClientePayload
  set: <K extends keyof ClientePayload>(chave: K, valor: ClientePayload[K]) => void
  grupos: Grupo[]
  readOnly: boolean
  podeEditar: boolean
  enviando: boolean
  labelSubmit: string
  onSubmit: (e: FormEvent) => void
}

export function ClienteFormFields({ form, set, grupos, readOnly: ro, podeEditar, enviando, labelSubmit, onSubmit }: ClienteFormFieldsProps) {
  const txt = (label: string, chave: keyof ClientePayload) => (
    <Input
      id={`c-${chave}`}
      label={label}
      value={(form[chave] as string | null) ?? ''}
      onChange={(e) => set(chave, (e.target.value || null) as ClientePayload[typeof chave])}
      disabled={ro}
    />
  )

  return (
    <form className="space-y-6" onSubmit={onSubmit}>
      <Secao titulo="Identificação">
        <Input id="c-nome" label="Nome" value={form.nome} onChange={(e) => set('nome', e.target.value)} required disabled={ro} />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Select id="c-grupo" label="Grupo" value={form.grupo ? String(form.grupo) : ''} onChange={(e) => set('grupo', e.target.value ? Number(e.target.value) : null)} disabled={ro}>
            <option value="">— sem grupo —</option>
            {grupos.map((g) => <option key={g.id} value={g.id}>{g.descricao}</option>)}
          </Select>
          <label className="flex items-center gap-2 text-sm text-slate-300 mt-6">
            <input type="checkbox" checked={form.ativo} onChange={(e) => set('ativo', e.target.checked)} disabled={ro} className="accent-primary" />
            Ativo
          </label>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Input
            id="c-cgc"
            label="CNPJ"
            value={mascararCNPJ(form.cgc ?? '')}
            onChange={(e) => set('cgc', soDigitos(e.target.value) || null)}
            disabled={ro}
          />
          <Input
            id="c-cpf"
            label="CPF"
            value={mascararCPF(form.cpf ?? '')}
            onChange={(e) => set('cpf', soDigitos(e.target.value) || null)}
            disabled={ro}
          />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">{txt('Inscrição municipal', 'insc_mun')}{txt('Inscrição estadual', 'insc_est')}</div>
      </Secao>

      <Secao titulo="Endereço">
        {txt('Logradouro', 'endereco')}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Input id="c-numero" label="Número" type="number" value={form.numero != null ? String(form.numero) : ''} onChange={(e) => set('numero', e.target.value ? Number(e.target.value) : null)} disabled={ro} />
          {txt('Complemento', 'complemento')}
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">{txt('Bairro', 'bairro')}{txt('CEP', 'cep')}</div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">{txt('Município', 'municipio')}{txt('UF', 'estado')}</div>
      </Secao>

      <Secao titulo="Contatos">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">{txt('Contato', 'contato')}{txt('E-mail', 'email')}</div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">{txt('Telefones', 'telefones')}{txt('Celular', 'celular')}</div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">{txt('WhatsApp', 'whatsapp')}{txt('WhatsApp 2', 'whatsapp1')}{txt('WhatsApp 3', 'whatsapp2')}</div>
      </Secao>

      <Secao titulo="Observações">
        <textarea
          value={form.obs ?? ''}
          onChange={(e) => set('obs', e.target.value || null)}
          disabled={ro}
          rows={3}
          className="w-full text-sm text-slate-200 bg-background-elevated border border-border rounded-lg px-3 py-2.5 resize-none focus:outline-none focus:ring-2 focus:ring-primary/40 placeholder-slate-500 leading-relaxed disabled:opacity-60"
        />
      </Secao>

      {podeEditar && (
        <button type="submit" disabled={enviando} className="w-full py-2.5 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary-600 disabled:opacity-60 transition-all">
          {labelSubmit}
        </button>
      )}
    </form>
  )
}
