import { useState } from 'react'
import { cn } from '../../lib/utils'
import { useAuth } from '../../auth/AuthContext'
import { isAdmin } from '../../auth/roles'
import { CadastroSimples } from './CadastroSimples'
import { GruposPanel } from './GruposPanel'
import { CategoriasPanel } from './CategoriasPanel'
import { EquipamentosPanel } from './EquipamentosPanel'
import { setoresApi, marcasApi, type Setor, type Marca } from './api'

const ABAS = ['Setores', 'Marcas', 'Grupos', 'Categorias', 'Equipamentos'] as const
type Aba = (typeof ABAS)[number]

export function CadastrosPage() {
  const { user } = useAuth()
  const [aba, setAba] = useState<Aba>('Setores')

  if (!isAdmin(user)) {
    return (
      <div className="px-4 md:px-6 py-6">
        <p className="text-sm text-slate-400">Acesso restrito a administradores.</p>
      </div>
    )
  }

  return (
    <div className="px-4 md:px-6 py-6 space-y-6">
      <h1 className="text-2xl font-extrabold text-slate-100">Cadastros</h1>
      <div className="flex flex-wrap gap-2">
        {ABAS.map((a) => (
          <button
            key={a}
            onClick={() => setAba(a)}
            className={cn(
              'text-xs px-3 py-1.5 rounded-full font-medium transition-all',
              aba === a ? 'bg-primary/15 text-primary' : 'text-slate-500 hover:text-slate-300 hover:bg-background-elevated',
            )}
          >
            {a}
          </button>
        ))}
      </div>
      <div className="rounded-2xl bg-background-surface border border-border p-5">
        {aba === 'Setores' && <CadastroSimples<Setor> titulo="Setores" client={setoresApi} />}
        {aba === 'Marcas' && <CadastroSimples<Marca> titulo="Marcas" client={marcasApi} />}
        {aba === 'Grupos' && <GruposPanel />}
        {aba === 'Categorias' && <CategoriasPanel />}
        {aba === 'Equipamentos' && <EquipamentosPanel />}
      </div>
    </div>
  )
}
