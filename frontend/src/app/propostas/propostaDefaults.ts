// Conteúdo padrão de novas propostas (módulo Serviço / Propostas).

// Escapa valores dinâmicos antes de interpolar no HTML do template (evita XSS/injeção;
// modelo/aparelhos vêm de dados digitados pelo laboratório).
const esc = (s: string): string =>
  s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

export const DEFAULT_NOTES =
  "Caso, durante o processo de calibração, seja identificado que o aparelho necessita de manutenção, a presente proposta será atualizada para incluir os serviços adicionais necessários, bem como os respectivos valores.";

/**
 * Template do campo "Outros itens ou serviços" (HTML para o react-quill).
 * `modelo` e `aparelhos` são dinâmicos — preenchidos com os dados do card
 * quando a proposta é criada de dentro dele; ficam em branco na proposta avulsa.
 */
export function buildDefaultOtherItems(modelo = "", aparelhos = ""): string {
  // Separador visual entre as seções (Quill descarta <hr>, então usamos uma linha
  // de traços em texto + linhas em branco para dar espaçamento).
  const HR = "<p><br></p><p>──────────────────────────────</p><p><br></p>";
  return `<p><strong>Serviços de Calibração e Manutenção</strong></p>
<p><strong>Modelo:</strong> ${esc(modelo)}<br><strong>Aparelhos:</strong> ${esc(aparelhos)}</p>${HR}<p><strong>Serviço Realizado:</strong></p>
<ul><li>Calibração</li></ul>
<p><strong>Valor Unitário da Calibração:</strong></p>
<ul><li>R$ 395,00</li></ul>${HR}<p><strong>Método de Envio:</strong></p>
<ul><li>SEDEX</li></ul>
<p><strong>Frete para entrega fixo:</strong></p>
<p>Região Norte: R$ 200,00<br>Região Nordeste: R$ 150,00<br>Região Sul: R$ 250,00<br>Região Sudeste: R$ 200,00<br>Região Centro-Oeste: R$ 200,00</p>${HR}<p><strong>Prazo de Entrega</strong></p>
<p>Norte: 15 a 22 dias úteis<br>Nordeste: 7 a 15 dias úteis<br>Sul: 7 dias úteis<br>Centro-Oeste: 7 a 15 dias úteis<br>Sudeste: 7 dias úteis</p>${HR}<p><strong>Códigos de Serviço – CNAEs Relacionados:</strong></p>
<p>33.12-102 – Manutenção e reparação de aparelhos e instrumentos de medida, teste e controle</p>
<p>14.01 – Lubrificação, limpeza, lubrificação, revisão, carga e recarga, conserto, restauração, blindagem, manutenção e conservação de máquinas, veículos, aparelhos, equipamentos, motores, elevadores ou de qualquer objeto (exceto peças e partes empregadas, que ficam sujeitas ao ICMS)</p>${HR}<p><strong>Endereço para o envio dos Aparelhos:</strong><br>Rua Viscondessa do Livramento, nº 54<br>Bairro: Derby<br>CEP: 52010-065<br>Recife – PE</p>
<p><br></p>
<p><strong>Contato – Setor de Calibração</strong><br>Telefone: (81) 3052-3350</p>`;
}

/**
 * Template do campo "Outros itens ou serviços" para o aparelho **Phoebus**
 * (Calibração Anual + Anuidade da Plataforma). Texto padrão com campos a preencher
 * manualmente (número do módulo, serial e valores).
 */
export function buildPhoebusOtherItems(serial = "", modulo = ""): string {
  const HR = "<p><br></p><p>──────────────────────────────</p><p><br></p>";
  const moduloTxt = modulo.trim() ? esc(modulo.trim()) : "[Inserir número]";
  const serialTxt = serial.trim() ? esc(serial.trim()) : "[Inserir número]";
  return `<p><strong>Calibração Anual e Anuidade da Plataforma do Aparelho Phoebus</strong></p>${HR}<p><strong>1. Informações do Aparelho</strong></p>
<ul><li><strong>Número do Módulo:</strong> ${moduloTxt}</li><li><strong>Serial do Aparelho:</strong> ${serialTxt}</li></ul>${HR}<p><strong>2. Periodicidade dos Serviços</strong></p>
<ul><li><strong>Calibração:</strong> realizada a cada 12 meses.</li><li><strong>Anuidade da Plataforma:</strong> renovação a cada 12 meses.</li></ul>${HR}<p><strong>3. Valores Referentes</strong></p>
<ul><li><strong>Calibração:</strong> R$ ____ (por unidade) + IPCA anual</li><li><strong>Anuidade Plataforma Web 2025:</strong> R$ ____ (por unidade) + IPCA anual</li></ul>${HR}<p><strong>4. Método de Envio</strong></p>
<ul><li><strong>Sedex</strong> – frete já incluso no valor da calibração.</li></ul>${HR}<p><strong>5. Código dos Serviços</strong></p>
<p><strong>Plataforma:</strong></p>
<ul><li><strong>Código:</strong> 01.05 – Licenciamento ou cessão de direito de uso de programas de computação</li><li><strong>CNAE:</strong> 6203-1/00 – Desenvolvimento e licenciamento de programas de computador não-customizáveis</li></ul>
<p><strong>Calibração:</strong></p>
<ul><li><strong>Código:</strong> 14.01 – Lubrificação, limpeza, lustração, revisão, carga e recarga, conserto, restauração, blindagem, manutenção e conservação de máquinas, veículos, aparelhos, equipamentos, motores, elevadores ou de qualquer objeto (exceto peças e partes empregadas, sujeitas ao ICMS)</li><li><strong>Serviço:</strong> Calibração – Manutenção e reparação de aparelhos e instrumentos de medida, teste e controle</li></ul>${HR}<p><strong>Prazo de Entrega</strong></p>
<p>Norte: 15 a 22 dias úteis<br>Nordeste: 7 a 15 dias úteis<br>Sul: 7 dias úteis<br>Centro-Oeste: 7 a 15 dias úteis<br>Sudeste: 7 dias úteis</p>${HR}<p><strong>Códigos de Serviço – CNAEs Relacionados:</strong></p>
<ul><li><strong>33.12-102</strong> – Manutenção e reparação de aparelhos e instrumentos de medida, teste e controle</li><li><strong>14.01</strong> – Lubrificação, limpeza, lubrificação, revisão, carga e recarga, conserto, restauração, blindagem, manutenção e conservação de máquinas, veículos, aparelhos, equipamentos, motores, elevadores ou de qualquer objeto (exceto peças e partes empregadas, que ficam sujeitas ao ICMS)</li></ul>${HR}<p><strong>Endereço para Devolução dos Aparelhos:</strong><br>Rua Viscondessa do Livramento, nº 54<br>Bairro: Derby<br>CEP: 52010-065<br>Recife – PE</p>${HR}<p><strong>6. Endereço para Envio do Material</strong><br>Rua Viscondessa do Livramento, 54 – Sala G<br>Bairro: Derby<br>CEP: 52010-065<br>Recife – PE</p>`;
}
