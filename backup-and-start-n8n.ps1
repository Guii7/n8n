# SCRIPT: backup-and-start-n8n.ps1
# Este script faz um backup dos volumes e depois inicia o N8N, garantindo a ordem e a robustez.

# Porta que o N8N está expondo localmente (verifique seu docker-compose.yml)
$n8nPort = "5678"

# Definir nomes dos volumes e diretório de backup
$n8nVolumeName = "n8n_n8n_data"
$postgresVolumeName = "n8n_postgres_data"
$backupDir = ".\backups"
$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$backupFileName = "n8n_backup_$timestamp.tar"

# Caminho padrão para o executável do Docker Desktop. Ajuste se o seu estiver em outro lugar!
$dockerDesktopPath = "C:\Program Files\Docker\Docker\Docker Desktop.exe"

# --- 1. Garantir que o Docker Desktop está rodando e pronto ---

Write-Host "Verificando se Docker Desktop está em execucao como processo..."
$dockerDesktopProcess = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue

if ($null -eq $dockerDesktopProcess) {
    Write-Host "Docker Desktop nao esta rodando. Tentando iniciar..."
    try {
        Start-Process -FilePath $dockerDesktopPath -WindowStyle Hidden -ErrorAction Stop
        Write-Host "Docker Desktop iniciado. Aguardando inicializacao do motor Docker..."
        Start-Sleep -Seconds 10
    } catch {
        Write-Error "Falha ao iniciar Docker Desktop. Verifique se o caminho esta correto: '$dockerDesktopPath' e se voce tem permissoes."
        exit 1
    }
} else {
    Write-Host "Docker Desktop ja esta em execucao como processo."
}

Write-Host "Verificando se Docker Desktop está pronto..."
$dockerReady = $false
$maxDockerAttempts = 20
$dockerAttempt = 0

while (-not $dockerReady -and $dockerAttempt -lt $maxDockerAttempts) {
    $dockerAttempt++
    Write-Host "Tentativa $dockerAttempt de $maxDockerAttempts para conectar ao Docker..."
    try {
        docker ps -q -a | Out-Null
        $dockerReady = $true
    } catch {
        Write-Warning "Docker Desktop ainda nao esta pronto ou inacessivel: $($_.Exception.Message)"
        Start-Sleep -Seconds 3
    }
}

if (-not $dockerReady) {
    Write-Error "Docker Desktop nao ficou acessivel apos varias tentativas. A tarefa falhou."
    exit 1
}

# --- 2. Realizar o Backup dos Volumes ---

Write-Host "Iniciando o processo de backup..."
Write-Host "Parando os containers para garantir um backup consistente..."
docker-compose down

if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir | Out-Null
    Write-Host "Diretório de backups criado em: $backupDir"
}

Write-Host "Criando backup dos volumes do N8N e PostgreSQL..."
try {
    docker run --rm `
    --volume ${n8nVolumeName}:/n8n `
    --volume ${postgresVolumeName}:/postgres `
    --volume "$(Get-Item -Path $backupDir).FullName":/backup `
    alpine tar czvf /backup/$backupFileName -C / n8n postgres

    Write-Host "Backup concluído com sucesso! Arquivo salvo em: $backupDir\$backupFileName"
}
catch {
    Write-Error "Ocorreu um erro durante o backup: $($_.Exception.Message). A tarefa falhou."
    exit 1
}

# --- 3. Iniciar o N8N e os Containers ---

Write-Host "Iniciando o processo de inicialização do N8N..."
# O script start-n8n.ps1 irá cuidar da inicialização do ngrok e dos containers.
. .\start-n8n.ps1

Write-Host "Backup e inicialização concluídos com sucesso!"
