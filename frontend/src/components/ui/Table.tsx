import { type ReactNode } from 'react'

interface TableProps {
  head: ReactNode
  children: ReactNode
}

export function Table({ head, children }: TableProps) {
  return (
    <div className="rounded-2xl border border-border bg-background-surface overflow-hidden shadow-sm">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-background-elevated">{head}</tr>
        </thead>
        <tbody className="divide-y divide-border">{children}</tbody>
      </table>
    </div>
  )
}

export function TH({ children }: { children: ReactNode }) {
  return <th className="text-left px-5 py-3 text-xs font-semibold uppercase tracking-wider text-slate-400">{children}</th>
}

export function TD({ children }: { children: ReactNode }) {
  return <td className="px-5 py-4">{children}</td>
}
