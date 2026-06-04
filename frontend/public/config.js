// Configuração de runtime do frontend.
// Em produção, o container sobrescreve este arquivo no boot com a env API_URL.
// Vazio = usa o fallback de build (VITE_API_URL) ou localhost (dev).
window.__API_URL__ = "";
