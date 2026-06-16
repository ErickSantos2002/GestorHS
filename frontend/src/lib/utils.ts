import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Formata uma data ISO para dd/mm/aaaa (pt-BR); '—' para nula/invalida. */
export function formatData(iso: string | null): string {
  if (!iso) return '—'
  // ISO date-only strings (YYYY-MM-DD) are parsed as UTC midnight by spec,
  // which shifts the day backwards in negative-offset timezones.
  // Appending T00:00:00 makes the parser treat it as local midnight.
  const normalized = /^\d{4}-\d{2}-\d{2}$/.test(iso) ? `${iso}T00:00:00` : iso
  const d = new Date(normalized)
  return isNaN(d.getTime()) ? '—' : d.toLocaleDateString('pt-BR')
}
