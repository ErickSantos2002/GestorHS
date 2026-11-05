// Espelho de `chave_de_acesso`/`nome_download_nota` em backend/app/core/nota_fiscal.py
// — mexer num, mexer no outro. O download e' feito por blob + `a.download`, entao
// o Content-Disposition do backend nao chega aqui e o nome e' montado do lado de ca.
//
// O XML sai como `<chave de acesso>.xml`: e' o nome original do emissor e o unico
// que o VIPP (postagem da expedicao) aceita — "nota-fiscal-..." ele recusa.
const CHAVE = /Id\s*=\s*["']NFe(\d{44})["']|<chNFe>\s*(\d{44})\s*<\/chNFe>/

export function chaveDeAcesso(xml: string): string | null {
  const m = CHAVE.exec(xml)
  return m ? (m[1] ?? m[2]) : null
}

/** Nome do XML baixado: a chave de acesso; sem ela (ex.: NFS-e), o `reserva`. */
export async function nomeDoXml(blob: Blob, reserva: string): Promise<string> {
  try {
    const chave = chaveDeAcesso(await blob.text())
    return chave ? `${chave}.xml` : reserva
  } catch {
    return reserva
  }
}
