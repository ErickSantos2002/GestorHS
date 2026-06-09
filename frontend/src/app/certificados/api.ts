import { apiJson, apiFetch, ApiError } from '../../lib/api'

async function apiVoid(path: string, options: RequestInit = {}): Promise<void> {
  const res = await apiFetch(path, options)
  if (!res.ok) {
    let detail = res.statusText
    try { const b = (await res.json()) as { detail?: string }; if (b.detail) detail = b.detail } catch { /* sem corpo */ }
    throw new ApiError(res.status, detail)
  }
}

export interface ModeloItem {
  equipamento: number
  equipamento_descricao: string | null
  tem_calibracao: boolean
  tem_manutencao: boolean
}
export interface CertificadoModelo {
  equipamento: number
  equipamento_descricao: string | null
  descricao: string | null
  texto: string
  tipo: 'C' | 'M'
}
export interface ImagemCert {
  id: number
  nome: string | null
  arquivo: string
  url: string
}

export const CAMPOS_CERTIFICADO: { campo: string; desc: string }[] = [
  { campo: '[nomecli]', desc: 'Nome do cliente' },
  { campo: '[cnpj]', desc: 'CNPJ/CPF do cliente' },
  { campo: '[endcli]', desc: 'Endereço do cliente' },
  { campo: '[modelo]', desc: 'Modelo do equipamento' },
  { campo: '[marca]', desc: 'Marca do equipamento' },
  { campo: '[serie]', desc: 'Número de série' },
  { campo: '[patrimonio]', desc: 'Patrimônio' },
  { campo: '[datacompra]', desc: 'Data de compra' },
  { campo: '[os]', desc: 'Número da OS' },
  { campo: '[calibcert]', desc: 'Nº do certificado' },
  { campo: '[datacalibracao]', desc: 'Data da calibração' },
  { campo: '[proxcalibragem]', desc: 'Próxima calibração' },
  { campo: '[tipocalibragem]', desc: 'Tipo de calibragem' },
  { campo: '[temperatura]', desc: 'Temperatura' },
  { campo: '[pressao]', desc: 'Pressão' },
  { campo: '[teste1]', desc: 'Teste 1' },
  { campo: '[teste2]', desc: 'Teste 2' },
  { campo: '[teste3]', desc: 'Teste 3' },
  { campo: '[media]', desc: 'Média dos testes' },
  { campo: '[situacao]', desc: 'Situação' },
  { campo: '[dataemissao]', desc: 'Data de emissão' },
]

export const certificadosApi = {
  listarModelos: (params: { q?: string } = {}): Promise<{ items: ModeloItem[] }> => {
    const sp = new URLSearchParams()
    if (params.q) sp.set('q', params.q)
    const qs = sp.toString()
    return apiJson<{ items: ModeloItem[] }>(`/certificados-modelo${qs ? `?${qs}` : ''}`)
  },
  obterModelo: (equipId: number, tipo: 'C' | 'M' = 'C'): Promise<CertificadoModelo> =>
    apiJson<CertificadoModelo>(`/certificados-modelo/${equipId}?tipo=${tipo}`),
  salvarModelo: (equipId: number, body: { descricao?: string | null; texto: string }, tipo: 'C' | 'M' = 'C'): Promise<CertificadoModelo> =>
    apiJson<CertificadoModelo>(`/certificados-modelo/${equipId}?tipo=${tipo}`, { method: 'PUT', body: JSON.stringify(body) }),
  listarImagens: (): Promise<{ items: ImagemCert[] }> =>
    apiJson<{ items: ImagemCert[] }>('/certificado-imagens'),
  enviarImagem: async (file: File, nome?: string): Promise<ImagemCert> => {
    const fd = new FormData()
    fd.append('file', file)
    if (nome) fd.append('nome', nome)
    const res = await apiFetch('/certificado-imagens', { method: 'POST', body: fd })
    if (!res.ok) {
      let detail = res.statusText
      try { const b = await res.json(); if (b.detail) detail = b.detail } catch { /* sem corpo */ }
      throw new ApiError(res.status, detail)
    }
    return (await res.json()) as ImagemCert
  },
  excluirImagem: (id: number): Promise<void> => apiVoid(`/certificado-imagens/${id}`, { method: 'DELETE' }),
}
