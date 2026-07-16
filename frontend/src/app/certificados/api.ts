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

export interface CertGeralItem {
  id: number
  nome: string
  data_upload: string | null
  usuario_nome: string | null
  link: string | null
}

export interface AvulsoItem {
  id: number
  tipo: 'C' | 'M'
  nomecli: string | null
  serie: string | null
  calib_cert: string | null
  data_calibracao: string | null
  data_geracao: string | null
  usuario_nome: string | null
}

export interface AvulsoPayload {
  equipamento: number       // o aparelho do template — [modelo]/[marca] saem do cadastro dele
  tipo: 'C' | 'M'
  nomecli?: string | null
  cnpj?: string | null
  endcli?: string | null
  serie?: string | null
  datacompra?: string | null
  os?: string | null
  data_recebimento?: string | null
  calib_cert?: string | null
  data_calibracao?: string | null
  calib_temp?: string | null
  calib_pressao?: string | null
  calib_teste1?: string | null
  calib_teste2?: string | null
  calib_teste3?: string | null
  calib_teste_media?: string | null
  calib_situacao?: string | null
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
  { campo: '[datacali]', desc: 'Data da calibração' },
  { campo: '[dataentr]', desc: 'Data de recebimento' },
  { campo: '[proxcalibragem]', desc: 'Próxima calibração' },
  { campo: '[tipocalibragem]', desc: 'Tipo de calibragem' },
  { campo: '[calibtemp]', desc: 'Temperatura' },
  { campo: '[calibpressao]', desc: 'Pressão' },
  { campo: '[calibteste1]', desc: 'Teste 1' },
  { campo: '[calibteste2]', desc: 'Teste 2' },
  { campo: '[calibteste3]', desc: 'Teste 3' },
  { campo: '[calibtestemedia]', desc: 'Média dos testes' },
  { campo: '[situcalib]', desc: 'Situação' },
  { campo: '[dataemissao]', desc: 'Data de emissão' },
  { campo: '[pulapagina]', desc: 'Quebra de página (impressão)' },
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

  listarGerais: (): Promise<CertGeralItem[]> => apiJson<CertGeralItem[]>('/certificados-gerais'),
  enviarGeral: async (nome: string, file: File): Promise<CertGeralItem> => {
    const fd = new FormData()
    fd.append('nome', nome)
    fd.append('arquivo', file)
    const res = await apiFetch('/certificados-gerais', { method: 'POST', body: fd })
    if (!res.ok) {
      let detail = res.statusText
      try { const b = await res.json(); if (b.detail) detail = b.detail } catch { /* sem corpo */ }
      throw new ApiError(res.status, detail)
    }
    return (await res.json()) as CertGeralItem
  },
  excluirGeral: (id: number): Promise<void> => apiVoid(`/certificados-gerais/${id}`, { method: 'DELETE' }),

  gerarAvulso: (payload: AvulsoPayload): Promise<AvulsoItem> =>
    apiJson<AvulsoItem>('/certificados-avulsos', { method: 'POST', body: JSON.stringify(payload) }),

  listarAvulsos: (): Promise<AvulsoItem[]> => apiJson<AvulsoItem[]>('/certificados-avulsos'),

  // Nunca abrir o PDF numa aba via blob: (herda a origem do app — vetor de XSS ja
  // corrigido nesta base). Forca download via link com atributo `download`, como
  // ordensApi.baixarCertificadoPdf.
  baixarAvulsoPdf: async (id: number): Promise<void> => {
    const res = await apiFetch(`/certificados-avulsos/${id}/pdf`)
    if (!res.ok) throw new ApiError(res.status, 'Falha ao baixar PDF')
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `certificado-avulso-${id}.pdf`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  },
}
