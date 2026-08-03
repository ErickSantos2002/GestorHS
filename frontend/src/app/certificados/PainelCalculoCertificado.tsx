import type { CalculoPrevia, CertificadoPadrao } from './api'

const secao = 'text-xs font-semibold text-slate-500 uppercase tracking-wide'

/** Bloco somente-leitura do calculo do EPS-LAB-002: erros por medicao, incerteza
 *  expandida, aviso de fora-da-faixa e a linha do cilindro que sera gravado.
 *
 *  Compartilhado entre `CamposCertificado` (OS e venda) e `CertificadoAvulsoModal`
 *  para nao duplicar essa apresentacao — os dois consomem `useCalculoCertificado`
 *  e passam o resultado aqui. Nenhum dos dois blocos bloqueia a geracao do
 *  certificado: um aparelho reprovado ou sem cilindro cadastrado tambem precisa
 *  sair com o documento.
 */
export function PainelCalculoCertificado({ previa, padroes, padrao }: {
  previa: CalculoPrevia | null
  padroes: CertificadoPadrao[] | null
  padrao: CertificadoPadrao | null
}) {
  return (
    <>
      {padroes !== null && (
        <p className="text-xs text-slate-400">
          {padrao ? (
            <>
              Cilindro que será gravado: <strong className="text-slate-200">{padrao.numero_cilindro}</strong>
              {' '}· certificado {padrao.numero_certificado ?? '—'}
              {' '}· {padrao.concentracao ?? '—'} {padrao.unidade ?? ''}
            </>
          ) : (
            <span className="text-amber-400">
              Nenhum cilindro cadastrado cobre esta data — a seção de padrões sairá em branco.
            </span>
          )}
        </p>
      )}
      {previa && (
        <div className="rounded-lg border border-slate-700 bg-background-elevated p-3 space-y-2">
          <p className={secao}>Cálculo (somente leitura)</p>
          {previa.fora_da_faixa.some(Boolean) && (
            <p className="text-xs text-red-400">
              Medição fora da faixa {previa.limite_minimo} – {previa.limite_maximo}. Confira antes de gerar.
            </p>
          )}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs text-slate-400">
            {previa.erros.map((erro, i) => (
              <span key={i}>Erro {i + 1}: <strong className="text-slate-200">{erro || '—'}</strong></span>
            ))}
          </div>
          <p className="text-xs text-slate-400">
            Incerteza expandida (U): <strong className="text-slate-200">{previa.incerteza_expandida}</strong>
            {' '}· k = {previa.fator_k} (95% de confiança)
          </p>
        </div>
      )}
    </>
  )
}
