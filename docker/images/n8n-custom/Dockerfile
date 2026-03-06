# Usa a imagem oficial do N8N 2.3.6+ como base
FROM n8nio/n8n:latest

# Adiciona permissões de root temporariamente para instalar dependências
USER root

# Baixar FFmpeg estático (binários compilados estaticamente, sem dependências)
RUN wget -O /tmp/ffmpeg.tar.xz https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz && \
    mkdir -p /tmp/ffmpeg && \
    tar -xf /tmp/ffmpeg.tar.xz -C /tmp/ffmpeg --strip-components=1 && \
    mv /tmp/ffmpeg/ffmpeg /usr/local/bin/ffmpeg && \
    mv /tmp/ffmpeg/ffprobe /usr/local/bin/ffprobe && \
    chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe && \
    rm -rf /tmp/ffmpeg /tmp/ffmpeg.tar.xz

# Cria diretório para Puppeteer e dá permissão ao node user
RUN mkdir -p /home/node/node_modules_external && \
    chown -R node:node /home/node/node_modules_external

# Volta para usuario node e instala Puppeteer
USER node
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
RUN cd /home/node/node_modules_external && \
    npm init -y && \
    npm install --save \
    puppeteer@24.38.0 \
    puppeteer-extra@3.3.6 \
    puppeteer-extra-plugin-stealth@2.11.2

# Define NODE_PATH para Puppeteer
ENV NODE_PATH=/home/node/node_modules_external/node_modules:/home/node/.node_modules

# Volta para root para criar diretório de vídeos
USER root
RUN mkdir -p /home/node/n8n_videos && \
    chown -R node:node /home/node/n8n_videos && \
    chmod -R 777 /home/node/n8n_videos

# Define workdir
WORKDIR /home/node

# Volta para o usuário padrão do N8N
USER node

# Define o diretório de trabalho
WORKDIR /home/node

# Expõe a porta padrão do N8N
EXPOSE 5678
