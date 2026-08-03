import type { CertificadoPadrao } from './api'

/** Resolução do cilindro padrão por data — espelho de `padrao_vigente()` em
 *  `backend/app/core/certificado_config.py`.
 *
 *  A regra inteira, incluindo o desempate, mora aqui e em nenhum outro lugar da tela:
 *  a aba Configurações usa para dizer qual cilindro está "Em uso" e o modal de gerar
 *  certificado usa para mostrar qual será gravado. Duas cópias da regra é o caminho
 *  para a tela afirmar um cilindro e o certificado sair com outro.
 *
 *  Datas são comparadas como texto ISO (`YYYY-MM-DD`), que ordena igual à data —
 *  é o formato em que a API devolve e evita fuso horário na conversão.
 */
export function padraoVigente(
  padroes: CertificadoPadrao[],
  data: string,
): CertificadoPadrao | null {
  const cobrem = padroes.filter(
    (p) =>
      p.ativo &&
      p.vigencia_inicio !== null &&
      p.vigencia_inicio <= data &&
      (p.vigencia_fim === null || p.vigencia_fim >= data),
  )
  if (cobrem.length === 0) return null
  // Mesmo desempate do backend: entre os que cobrem a data, o de vigência mais
  // recente (`ORDER BY vigencia_inicio DESC, id DESC`). É o que faz o fluxo esperado
  // — cadastrar o cilindro novo e deixar o antigo em aberto — apontar um só vigente.
  return cobrem.reduce((melhor, p) => {
    const inicioMelhor = melhor.vigencia_inicio ?? ''
    const inicioP = p.vigencia_inicio ?? ''
    if (inicioP > inicioMelhor) return p
    if (inicioP === inicioMelhor && p.id > melhor.id) return p
    return melhor
  })
}
