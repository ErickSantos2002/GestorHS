import ReactQuill from 'react-quill-new'
import 'react-quill-new/dist/quill.snow.css'

// Wrapper fino sobre react-quill-new (editor rico usado em intro/observacoes das
// propostas tecnicas). So e montado nas paginas do modulo — nao entra nos testes
// de api.ts, entao problemas de import em ambiente de teste (jsdom/SSR) nao afetam
// a suite de `propostas/api.test.ts`.
export interface RichTextProps {
  value: string
  onChange: (html: string) => void
  placeholder?: string
}

export function RichText({ value, onChange, placeholder }: RichTextProps) {
  return (
    <ReactQuill
      theme="snow"
      value={value}
      onChange={onChange}
      placeholder={placeholder}
    />
  )
}
