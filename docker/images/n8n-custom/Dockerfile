# Usa a imagem oficial do N8N como base
FROM n8nio/n8n:latest

USER root

# Adiciona repositório Edge do Alpine para FFmpeg 8.0.1
RUN echo "https://dl-cdn.alpinelinux.org/alpine/edge/main" >> /etc/apk/repositories && \
    echo "https://dl-cdn.alpinelinux.org/alpine/edge/community" >> /etc/apk/repositories

# Instala o Chromium, FFmpeg 8.0.1 e dependências necessárias para o Puppeteer
RUN apk add --no-cache \
    chromium \
    nss \
    freetype \
    harfbuzz \
    ca-certificates \
    ttf-freefont \
    nodejs \
    yarn \
    ffmpeg

# Define a variável de ambiente para o Puppeteer usar o Chromium instalado
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser

# Cria diretório customizado para módulos externos e instala Puppeteer lá
RUN mkdir -p /usr/local/lib/node_modules_external && \
    cd /usr/local/lib/node_modules_external && \
    npm init -y && \
    npm install --save \
        puppeteer@22.0.0 \
        puppeteer-extra@3.3.6 \
        puppeteer-extra-plugin-stealth@2.11.2

# Cria symlinks para que o vm2 encontre os módulos
RUN ln -sf /usr/local/lib/node_modules_external/node_modules/puppeteer /usr/local/lib/node_modules/puppeteer && \
    ln -sf /usr/local/lib/node_modules_external/node_modules/puppeteer-extra /usr/local/lib/node_modules/puppeteer-extra && \
    ln -sf /usr/local/lib/node_modules_external/node_modules/puppeteer-extra-plugin-stealth /usr/local/lib/node_modules/puppeteer-extra-plugin-stealth

# Adiciona o diretório de módulos externos ao NODE_PATH
ENV NODE_PATH=/usr/local/lib/node_modules_external/node_modules:/usr/local/lib/node_modules

# Cria diretório para vídeos temporários com permissões adequadas
RUN mkdir -p /home/node/n8n_videos && \
    chown -R node:node /home/node/n8n_videos && \
    chmod -R 777 /home/node/n8n_videos

# Volta para o usuário padrão do N8N
WORKDIR /home/node
USER node

# Define o diretório de trabalho
WORKDIR /home/node

# Expõe a porta padrão do N8N
EXPOSE 5678
