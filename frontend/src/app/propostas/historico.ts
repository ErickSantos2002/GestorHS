// Lógica pura do histórico de propostas: comparação de snapshots entre versões.
// Fica isolada de React/HTTP para ser testável (ver historico.test.ts).

import { formatarMoeda } from '../../lib/moeda'

export interface SnapshotItem {
  descricao: string
  sku: string | null
  quantidade: number
  unidade: string | null
  preco_un: number
  total: number
}

// Espelha o dict de `snapshot_proposta` em
// backend/app/core/proposta_servico.py — mudou lá, ajuste aqui.
export interface Snapshot {
  numero: number
  data: string | null
  cliente_nome: string | null
  cliente_documento?: string | null
  total: number
  total_itens: number
  desconto: number
  frete: number
  itens: SnapshotItem[]
}

const moeda = formatarMoeda

function qtd(v: number): string {
  return Number.isInteger(v) ? String(v) : String(v).replace('.', ',')
}

function chaveItem(i: SnapshotItem): string {
  return `${(i.sku ?? '').trim().toLowerCase()}|${i.descricao.trim().toLowerCase()}`
}

/**
 * Coage um snapshot cru (JSON do backend, `Record<string, unknown> | null`) para
 * o formato `Snapshot`, preenchendo defaults. Retorna null se não houver dados.
 */
export function coerceSnapshot(raw: unknown): Snapshot | null {
  if (!raw || typeof raw !== 'object') return null
  const o = raw as Record<string, unknown>
  const num = (v: unknown): number => (typeof v === 'number' ? v : Number(v) || 0)
  const itensRaw = Array.isArray(o.itens) ? o.itens : []
  return {
    numero: num(o.numero),
    data: (o.data as string) ?? null,
    cliente_nome: (o.cliente_nome as string) ?? null,
    cliente_documento: (o.cliente_documento as string) ?? null,
    total: num(o.total),
    total_itens: num(o.total_itens),
    desconto: num(o.desconto),
    frete: num(o.frete),
    itens: itensRaw.map((it) => {
      const i = it as Record<string, unknown>
      return {
        descricao: String(i.descricao ?? ''),
        sku: (i.sku as string) ?? null,
        quantidade: num(i.quantidade),
        unidade: (i.unidade as string) ?? null,
        preco_un: num(i.preco_un),
        total: num(i.total),
      }
    }),
  }
}

/**
 * Compara dois snapshots (o `anterior` = versão mais antiga, `atual` = mais nova)
 * e devolve as diferenças legíveis, uma por string. Lista vazia = nada mudou.
 */
export function diffSnapshots(anterior: Snapshot, atual: Snapshot): string[] {
  const linhas: string[] = []

  if (anterior.frete !== atual.frete) {
    linhas.push(`Frete: ${moeda(anterior.frete)} → ${moeda(atual.frete)}`)
  }
  if (anterior.desconto !== atual.desconto) {
    linhas.push(`Desconto: ${moeda(anterior.desconto)} → ${moeda(atual.desconto)}`)
  }

  const antMap = new Map(anterior.itens.map((i) => [chaveItem(i), i]))
  const atuMap = new Map(atual.itens.map((i) => [chaveItem(i), i]))

  for (const it of atual.itens) {
    const antes = antMap.get(chaveItem(it))
    if (!antes) {
      linhas.push(`Item adicionado: ${it.descricao} ×${qtd(it.quantidade)}`)
      continue
    }
    if (antes.quantidade !== it.quantidade) {
      linhas.push(`Quantidade de "${it.descricao}": ${qtd(antes.quantidade)} → ${qtd(it.quantidade)}`)
    }
    if (antes.preco_un !== it.preco_un) {
      linhas.push(`Preço de "${it.descricao}": ${moeda(antes.preco_un)} → ${moeda(it.preco_un)}`)
    }
  }

  for (const it of anterior.itens) {
    if (!atuMap.has(chaveItem(it))) {
      linhas.push(`Item removido: ${it.descricao} ×${qtd(it.quantidade)}`)
    }
  }

  if (linhas.length === 0 && anterior.total !== atual.total) {
    // fallback: mudança de total sem causa granular identificada
    linhas.push(`Total: ${moeda(anterior.total)} → ${moeda(atual.total)}`)
  }

  return linhas
}
