#!/bin/sh
# Gera /config.js com a URL da API a partir da env de runtime API_URL.
# Roda no boot do container (nginx executa os scripts de /docker-entrypoint.d/).
# Permite trocar a URL da API sem rebuildar o frontend — basta mudar API_URL e reiniciar.
set -e

cat > /usr/share/nginx/html/config.js <<EOF
window.__API_URL__ = "${API_URL:-}";
EOF

echo "[runtime-config] API_URL='${API_URL:-}' gravada em /config.js"
