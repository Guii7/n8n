# Comece com a imagem base do N8N
FROM n8nio/n8n:latest

# Mude para o usuário root para instalar os pacotes do sistema
USER root

# Instala o Chromium e suas dependências
RUN apk add --no-cache \
    chromium \
    nss \
    freetype \
    harfbuzz \
    udev \
    ttf-freefont

# Instala TODAS as bibliotecas puppeteer necessárias GLOBALMENTE
RUN npm install -g puppeteer puppeteer-extra puppeteer-extra-plugin-stealth

# Retorna para o usuário 'node' padrão do N8N
USER node

# Define a variável de ambiente para o Puppeteer usar o Chromium do sistema
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser
