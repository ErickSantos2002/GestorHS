import { useState } from 'react'
import { cn } from '../../lib/utils'
import { ModelosTab } from './ModelosTab'
import { ImagensTab } from './ImagensTab'
import { AvulsosTab } from './AvulsosTab'
import { CertificadosGeraisTab } from './CertificadosGeraisTab'
import { PageContainer } from '../../components/ui/Page'

const ABAS = ['Modelos', 'Imagens', 'Em branco', 'Gerais'] as const
type Aba = (typeof ABAS)[number]

export function CertificadosPage() {
  const [aba, setAba] = useState<Aba>('Modelos')
  return (
    <PageContainer>
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100">Certificados</h1>
        <p className="text-sm text-slate-500 mt-0.5">Modelos de certificado por aparelho, biblioteca de imagens e certificados em branco.</p>
      </div>
      <div className="flex gap-2">
        {ABAS.map((a) => (
          <button key={a} onClick={() => setAba(a)}
            className={cn('text-xs px-3 py-1.5 rounded-full font-medium transition-all',
              aba === a ? 'bg-primary/15 text-primary' : 'text-slate-500 hover:text-slate-300 hover:bg-background-elevated')}>
            {a}
          </button>
        ))}
      </div>
      {aba === 'Modelos' ? <ModelosTab /> : aba === 'Imagens' ? <ImagensTab /> : aba === 'Em branco' ? <AvulsosTab /> : <CertificadosGeraisTab />}
    </PageContainer>
  )
}
