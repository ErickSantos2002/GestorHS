/** Utilitarios de CNPJ/CPF (documento). Storage e' sempre so digitos; formata nas pontas. */
export function soDigitos(v: string | null | undefined): string {
  return (v ?? '').replace(/\D/g, '')
}

/** Exibicao: 14 dig -> CNPJ, 11 dig -> CPF, qualquer outro tamanho -> os digitos como estao. */
export function formatarDocumento(v: string | null | undefined): string {
  const d = soDigitos(v)
  if (d.length === 14) return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}`
  if (d.length === 11) return `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6, 9)}-${d.slice(9)}`
  return d
}

/** Mascara progressiva de CNPJ para input (capa em 14 digitos). */
export function mascararCNPJ(v: string | null | undefined): string {
  const d = soDigitos(v).slice(0, 14)
  if (d.length > 12) return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}`
  if (d.length > 8) return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8)}`
  if (d.length > 5) return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5)}`
  if (d.length > 2) return `${d.slice(0, 2)}.${d.slice(2)}`
  return d
}

/** Mascara progressiva de CPF para input (capa em 11 digitos). */
export function mascararCPF(v: string | null | undefined): string {
  const d = soDigitos(v).slice(0, 11)
  if (d.length > 9) return `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6, 9)}-${d.slice(9)}`
  if (d.length > 6) return `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6)}`
  if (d.length > 3) return `${d.slice(0, 3)}.${d.slice(3)}`
  return d
}

/** Mascara progressiva de CEP para input (capa em 8 digitos). */
export function mascararCEP(v: string | null | undefined): string {
  const d = soDigitos(v).slice(0, 8)
  return d.length > 5 ? `${d.slice(0, 5)}-${d.slice(5)}` : d
}
