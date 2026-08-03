import { useEffect, useState } from 'react'
import { certificadosApi, type CalculoPrevia, type CertificadoPadrao } from './api'
import { padraoVigente } from './padraoVigente'

/** Previa de calculo (EPS-LAB-002) e cilindro vigente, compartilhados entre todo
 *  formulario que oferece as 5 medicoes: a OS (via `CamposCertificado`) e o modal
 *  de certificado avulso. Os dois efeitos aqui sao informativos por design — uma
 *  falha na previa ou na lista de cilindros nao pode travar a geracao do certificado,
 *  entao ambos engolem o erro e caem para `null`.
 *
 *  `ativo=false` desliga os dois fetches (usado por `CamposCertificado` quando
 *  `medicoes !== 5`, onde nem previa nem cilindro fazem sentido).
 */
export function useCalculoCertificado(
  medicoesValores: string[],
  dataCalib: string,
  ativo: boolean = true,
): { previa: CalculoPrevia | null; padroes: CertificadoPadrao[] | null; padrao: CertificadoPadrao | null } {
  const chaveMedicoes = medicoesValores.join('|')
  // A previa so faz sentido com pelo menos uma medicao preenchida; deriva do estado
  // em vez de zerar via setState sincrono no corpo do efeito (react-hooks/set-state-in-effect).
  const mostrarPrevia = ativo && !medicoesValores.every((m) => m.trim() === '')

  const [previaBruta, setPrevia] = useState<CalculoPrevia | null>(null)
  const previa = mostrarPrevia ? previaBruta : null

  useEffect(() => {
    if (!mostrarPrevia) return
    const timer = setTimeout(() => {
      certificadosApi.calculoPrevia(medicoesValores)
        .then(setPrevia)
        .catch(() => setPrevia(null))
    }, 400)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chaveMedicoes, mostrarPrevia])

  // Cilindro que sera gravado nesta geracao. A lista vem inteira e a resolucao roda
  // aqui porque a data de calibracao e editavel no proprio formulario.
  const [padroes, setPadroes] = useState<CertificadoPadrao[] | null>(null)
  useEffect(() => {
    if (!ativo) return
    let vivo = true
    certificadosApi.padroes()
      .then((lista) => { if (vivo) setPadroes(lista) })
      .catch(() => { if (vivo) setPadroes(null) })
    return () => { vivo = false }
  }, [ativo])
  const padrao = padroes ? padraoVigente(padroes, dataCalib) : null

  return { previa, padroes, padrao }
}
