# Caminho para o executável do Ngrok. ALtere se o seu estiver em outro lugar!
$ngrokPath = "C:\Users\guii7\ngrok"

# Porta que o N8N está expondo localmente (verifique seu docker-compose.yml)
$n8nPort = "5678"

# --- Iniciar Ngrok em segundo plano e capturar o URL ---

Write-Host "Iniciando Ngrok e obtendo URL..."

# Inicia o Ngrok em uma nova janela oculta e redireciona a saída para um arquivo temporário
# -log=stdout direciona logs para stdout
# -log-level=info para não poluir muito
# -log-format=json para facilitar a leitura por script
$ngrokProcess = Start-Process -FilePath $ngrokPath -ArgumentList "http $n8nPort --log=stdout --log-level=info --log-format=json" -NoNewWindow -PassThru -RedirectStandardOutput ([System.IO.Path]::GetTempFileName()) -RedirectStandardError ([System.IO.Path]::GetTempFileName())
Start-Sleep -Seconds 5 # Espera um pouco para o Ngrok inicializar e gerar a URL

# Lê o arquivo de log do Ngrok para encontrar o URL HTTPS
$ngrokLogContent = Get-Content -Path $ngrokProcess.StandardOutput -Raw | ConvertFrom-Json
$publicUrl = $ngrokLogContent | Where-Object { $_.msg -eq "started tunnel" -and $_.url -like "https://*" } | Select-Object -ExpandProperty url -First 1

if ($null -eq $publicUrl) {
    Write-Error "Não foi possível obter a URL pública do Ngrok. Verifique se o Ngrok está configurado corretamente e se está gerando URLs."
    Read-Host "Pressione Enter para sair."
    exit 1
}

Write-Host "URL Pública do Ngrok obtida: $publicUrl"

# --- Definir a variável de ambiente para o Docker Compose ---

# Define a variável de ambiente para a sessão atual do PowerShell
$env:N8N_PUBLIC_URL = $publicUrl

Write-Host "Variável N8N_PUBLIC_URL definida: $env:N8N_PUBLIC_URL"

# --- Derrubar e Subir os containers Docker Compose ---

Write-Host "Parando containers Docker Compose existentes..."
docker-compose down # Não usamos --volumes aqui para não perder os dados do N8N e PG
Write-Host "Iniciando containers Docker Compose com a nova URL..."
docker-compose up -d

Write-Host "Automação concluída!"
Write-Host "Seu N8N deve estar acessível em: $publicUrl"
Write-Host "O Ngrok está rodando em segundo plano. Para pará-lo, você precisará fechar a tarefa ngrok.exe no Gerenciador de Tarefas."

Read-Host "Pressione Enter para sair."
