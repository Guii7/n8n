# Caminho para o executável do Ngrok. ALtere se o seu estiver em outro lugar!
$ngrokPath = "C:\Users\guii7\ngrok\ngrok.exe" # Exemplo: ajuste para o seu caminho real

# Porta que o N8N está expondo localmente (verifique seu docker-compose.yml)
$n8nPort = "5678"

# --- Iniciar Ngrok em segundo plano e capturar o URL ---

Write-Host "Iniciando Ngrok e obtendo URL..."

# Define os caminhos para os arquivos de log temporários (UM PARA CADA SAÍDA)
$tempLogOutputPath = [System.IO.Path]::GetTempFileName()
$tempLogErrorPath = [System.IO.Path]::GetTempFileName() # NOVO ARQUIVO PARA ERROS

Write-Host "Arquivo de log de Saída do Ngrok: $tempLogOutputPath"
Write-Host "Arquivo de log de Erros do Ngrok: $tempLogErrorPath"

# Inicia o Ngrok em uma nova janela oculta e redireciona a saída para os arquivos temporários
$ngrokProcess = Start-Process -FilePath $ngrokPath `
    -ArgumentList "http $n8nPort --log=stdout --log-level=info --log-format=json" `
    -NoNewWindow -PassThru `
    -RedirectStandardOutput $tempLogOutputPath `
    -RedirectStandardError $tempLogErrorPath # AGORA REDIRECIONANDO PARA O NOVO ARQUIVO

# Verifica se o processo Ngrok foi iniciado com sucesso
if ($null -eq $ngrokProcess) {
    Write-Error "Falha ao iniciar o processo do Ngrok. Verifique o caminho do Ngrok e as permissões."
    Read-Host "Pressione Enter para sair."
    exit 1
}

Write-Host "Processo Ngrok iniciado. Aguardando a URL..."

# Loop para esperar e ler a URL do Ngrok do arquivo de log de saída
$publicUrl = $null
$maxAttempts = 30 # Tenta por até 30 * 2 = 60 segundos
$attempt = 0

while ($null -eq $publicUrl -and $attempt -lt $maxAttempts) {
    Start-Sleep -Seconds 2 # Espera 2 segundos antes de cada tentativa de leitura
    $attempt++
    Write-Host "Tentativa $attempt de $maxAttempts para ler o log do Ngrok..."

    # Lê o conteúdo do arquivo de log de saída e tenta encontrar a URL
    try {
        # Apenas lemos do arquivo de SAÍDA PADRÃO
        $ngrokLogContent = Get-Content -Path $tempLogOutputPath -ErrorAction SilentlyContinue | ConvertFrom-Json -ErrorAction SilentlyContinue
        if ($null -ne $ngrokLogContent) {
            $publicUrl = $ngrokLogContent | Where-Object { $_.msg -eq "started tunnel" -and $_.url -like "https://*" } | Select-Object -ExpandProperty url -First 1
        }
    } catch {
        Write-Warning "Erro ao processar o log do Ngrok: $($_.Exception.Message)"
    }
}

# Limpa os arquivos de log temporários (opcional, pode ser útil para depuração deixar)
Remove-Item -Path $tempLogOutputPath -ErrorAction SilentlyContinue
Remove-Item -Path $tempLogErrorPath -ErrorAction SilentlyContinue

if ($null -eq $publicUrl) {
    Write-Error "Não foi possível obter a URL pública do Ngrok após várias tentativas. Verifique se o Ngrok está configurado corretamente e se está gerando URLs."
    Write-Host "Conteúdo final do log de SAÍDA (se existir):"
    Get-Content -Path $tempLogOutputPath -ErrorAction SilentlyContinue
    Write-Host "Conteúdo final do log de ERROS (se existir):"
    Get-Content -Path $tempLogErrorPath -ErrorAction SilentlyContinue
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
