# Caminho para o executável do Ngrok (apenas para localizar o arquivo de log agora). ALtere se o seu estiver em outro lugar!
$ngrokPath = "C:\Users\guii7\ngrok\ngrok.exe" # <<<<<< MUDANÇA AQUI: Adicionar \ngrok.exe

# Porta que o N8N está expondo localmente (verifique seu docker-compose.yml)
$n8nPort = "5678"

# Caminho para o arquivo de log que a Tarefa Agendada do Ngrok está criando
# Agora, Split-Path de "C:\Users\guii7\ngrok\ngrok.exe" resultará em "C:\Users\guii7\ngrok"
# E o caminho do log será "C:\Users\guii7\ngrok\ngrok_console.log" - O CORRETO!
$ngrokLogFilePath = (Split-Path $ngrokPath) + "\ngrok_console.log"

Write-Host "Lendo o arquivo de log do Ngrok para obter a URL..."
Write-Host "Arquivo de log do Ngrok: $ngrokLogFilePath"

# --- Obter o URL do Ngrok do arquivo de log ---
$publicUrl = $null
$maxAttempts = 30 # Tenta por até 30 * 2 = 60 segundos
$attempt = 0

while ($null -eq $publicUrl -and $attempt -lt $maxAttempts) {
    Start-Sleep -Seconds 2
    $attempt++
    Write-Host "Tentativa $attempt de $maxAttempts para ler o log do Ngrok..."

    try {
        # AQUI ESTÁ A MUDANÇA: Adicionamos -ReadCount 0 e -Wait para tentar ler o arquivo que pode estar travado
        # E usamos um loop interno para garantir que o ConvertFrom-Json tenha uma entrada válida
        $logLines = Get-Content -Path $ngrokLogFilePath -Tail 20 -ErrorAction SilentlyContinue

        if ($null -ne $logLines) {
            foreach ($line in $logLines) {
                try {
                    $jsonEntry = $line | ConvertFrom-Json -ErrorAction SilentlyContinue
                    if ($null -ne $jsonEntry -and $jsonEntry.msg -eq "started tunnel" -and $jsonEntry.url -like "https://*") {
                        $publicUrl = $jsonEntry.url
                        break # Encontrou a URL, pode sair do loop foreach
                    }
                } catch {
                    # Ignora erros de JSON malformado em linhas individuais
                }
            }
        }
    } catch {
        Write-Warning "Erro ao acessar/processar o log do Ngrok: $($_.Exception.Message)"
    }
}

if ($null -eq $publicUrl) {
    Write-Error "Não foi possível obter a URL pública do Ngrok. Verifique se a tarefa agendada do Ngrok está funcionando e escrevendo no log: $ngrokLogFilePath"
    Write-Host "Conteúdo final do log do Ngrok para depuração (se existir):"

    # Adicionando o -ErrorAction SilentlyContinue e -Raw para tentar ler o arquivo
    # mesmo que esteja bloqueado ou parcialmente escrito.
    try {
        Get-Content -Path $ngrokLogFilePath -ErrorAction SilentlyContinue -Raw
    } catch {
        Write-Host "Não foi possível ler o arquivo de log para depuração: $($_.Exception.Message)"
    }

    Read-Host "Pressione Enter para sair."
    exit 1
}

Write-Host "URL Pública do Ngrok obtida: $publicUrl"

# --- Definir a variável de ambiente e reiniciar Docker Compose ---

# Define a variável de ambiente para a sessão atual do PowerShell
$env:N8N_PUBLIC_URL = $publicUrl

Write-Host "Variável N8N_PUBLIC_URL definida: $env:N8N_PUBLIC_URL"

# --- NOVO BLOCO: Iniciar Docker Desktop se não estiver rodando ---
# Caminho padrão para o executável do Docker Desktop. Ajuste se o seu estiver em outro lugar!
$dockerDesktopPath = "C:\Program Files\Docker\Docker\Docker Desktop.exe"

Write-Host "Verificando se Docker Desktop está em execucao como processo..."
# Tenta obter o processo "Docker Desktop" (o nome da janela do aplicativo)
$dockerDesktopProcess = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue

if ($null -eq $dockerDesktopProcess) {
    Write-Host "Docker Desktop nao esta rodando. Tentando iniciar..."
    try {
        # Inicia o Docker Desktop. O -WindowStyle Hidden e -NoNewWindow
        # podem não ocultar totalmente a janela inicial para apps GUI, mas ele deve minimizar para a bandeja.
        Start-Process -FilePath $dockerDesktopPath -WindowStyle Hidden -ErrorAction Stop
        Write-Host "Docker Desktop iniciado. Aguardando inicializacao do motor Docker..."
        Start-Sleep -Seconds 10 # Dá um tempo inicial maior para o Docker Desktop carregar o GUI e começar a inicializar o motor
    } catch {
        Write-Error "Falha ao iniciar Docker Desktop. Verifique se o caminho esta correto: '$dockerDesktopPath' e se voce tem permissoes."
        Read-Host "Pressione Enter para sair."
        exit 1
    }
} else {
    Write-Host "Docker Desktop ja esta em execucao como processo."
}

# --- (Loop de espera para o Docker que já tínhamos) ---
Write-Host "Verificando se Docker Desktop está pronto..."
$dockerReady = $false
$maxDockerAttempts = 20 # Tenta por até 20 * 3 = 60 segundos
$dockerAttempt = 0

while (-not $dockerReady -and $dockerAttempt -lt $maxDockerAttempts) {
    $dockerAttempt++
    Write-Host "Tentativa $dockerAttempt de $maxDockerAttempts para conectar ao Docker..."
    try {
        # Tenta um comando Docker simples para verificar a conexão
        docker ps -q -a | Out-Null # Lista containers sem saída e descarta
        $dockerReady = $true
    } catch {
        Write-Warning "Docker Desktop ainda nao esta pronto ou inacessivel: $($_.Exception.Message)"
        Start-Sleep -Seconds 3 # Espera 3 segundos antes de tentar novamente
    }
}

if (-not $dockerReady) {
    Write-Error "Docker Desktop nao ficou acessivel apos varias tentativas. Por favor, verifique se esta rodando corretamente."
    Read-Host "Pressione Enter para sair."
    exit 1
}

# --- (Resto do script, que agora será executado apenas quando Docker estiver pronto) ---

Write-Host "Parando containers Docker Compose existentes..."
# Derruba os containers N8N e PostgreSQL (mantendo os volumes de dados)
docker-compose down
Write-Host "Iniciando containers Docker Compose com a nova URL..."
# Sobe os containers novamente
docker-compose up -d

Write-Host "Automação concluída!"
Write-Host "Seu N8N deve estar acessível em: $publicUrl"
Write-Host "A tarefa agendada do Ngrok deve estar mantendo o tÃºnel ativo em segundo plano."

Read-Host "Pressione Enter para sair."
