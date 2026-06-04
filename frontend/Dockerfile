# GestorHS — Frontend (SPA React) servido por nginx.
# Build multi-stage: compila com Node, serve os estáticos com nginx.

# --- Stage 1: build ---
FROM node:20-alpine AS build
WORKDIR /app

# Dependências primeiro (camada cacheável)
COPY package*.json ./
RUN npm ci

# Código e build
COPY . .

# URL da API embutida no bundle EM TEMPO DE BUILD (Vite injeta VITE_* do ambiente).
# No EasyPanel, defina VITE_API_URL como build arg/env apontando para a API de produção
# (ex.: https://api.seu-dominio.com). O default abaixo só serve para build local.
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# --- Stage 2: runtime (nginx) ---
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
