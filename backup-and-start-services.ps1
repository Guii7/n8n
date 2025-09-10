# SCRIPT: backup-and-start-services.ps1
# Este script faz backup completo dos volumes e inicia N8N + Evolution API

# Parâmetros de configuração
param(
    [switch]$SkipBackup = $false  # Use -SkipBackup para pular o backup
)

# Configurações
$workingDir = "C:\Users\guii7\n8n\n8n"
$logPath = "$workingDir\task_log.txt"
$backupDir = "$workingDir\backups"
$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$backupFileName = "integrated_backup_$timestamp.tar.gz"
$dockerDesktopPath = "C:\Program Files\Docker\Docker\Docker Desktop.exe"

# Volumes para backup (atualizados para a nova configuração)
$volumes = @{
    "n8n_data" = "n8n"
    "postgres_data" = "postgres"
    "evolution_redis" = "redis"
    "evolution_instances" = "evolution"
}

# Portas dos serviços
$n8nPort = "5678"
$evolutionPort = "8080"

# === INÍCIO DO LOG ===
Start-Transcript -Path $logPath -Append
Write-Host "=== INÍCIO DA EXECUÇÃO: $(Get-Date) ==="

# Mudar para o diretório de trabalho
try {
    Set-Location -Path $workingDir -ErrorAction Stop
    Write-Host "Diretório de trabalho: $(Get-Location)"
} catch {
    Write-Error "Falha ao acessar diretório: $workingDir"
    Stop-Transcript
    exit 1
}

# === 1. VERIFICAR E INICIAR DOCKER DESKTOP ===
Write-Host "Verificando Docker Desktop..."

$dockerProcess = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue
if ($null -eq $dockerProcess) {
    Write-Host "Docker Desktop não está rodando. Iniciando..."
    try {
        Start-Process -FilePath $dockerDesktopPath -WindowStyle Hidden
        Write-Host "Aguardando inicialização do Docker Desktop..."
        Start-Sleep -Seconds 15
    } catch {
        Write-Error "Falha ao iniciar Docker Desktop: $($_.Exception.Message)"
        Stop-Transcript
        exit 1
    }
} else {
    Write-Host "Docker Desktop já está em execução."
}

# Aguardar Docker estar pronto
Write-Host "Verificando se Docker está acessível..."
$dockerReady = $false
$maxAttempts = 30
$attempt = 0

while (-not $dockerReady -and $attempt -lt $maxAttempts) {
    $attempt++
    Write-Host "Tentativa $attempt de $maxAttempts..."
    try {
        $null = docker version --format '{{.Server.Version}}' 2>$null
        if ($LASTEXITCODE -eq 0) {
            $dockerReady = $true
            Write-Host "Docker está pronto!"
        }
    } catch {
        Write-Warning "Docker ainda não está pronto..."
    }

    if (-not $dockerReady) {
        Start-Sleep -Seconds 5
    }
}

if (-not $dockerReady) {
    Write-Error "Docker não ficou acessível após $maxAttempts tentativas."
    Stop-Transcript
    exit 1
}

# === 2. BACKUP DOS VOLUMES ===
if (-not $SkipBackup) {
    Write-Host "=== INICIANDO BACKUP ==="

    # Parar containers para backup consistente
    Write-Host "Parando containers..."
    docker-compose down
    Start-Sleep -Seconds 5

    # Criar diretório de backup
    if (-not (Test-Path $backupDir)) {
        New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
        Write-Host "Diretório de backup criado: $backupDir"
    }

    # Construir comando de volumes para o backup
    $volumeArgs = @()
    foreach ($volume in $volumes.GetEnumerator()) {
        $volumeArgs += "--volume"
        $volumeArgs += "$($volume.Key):/$($volume.Value)"
    }

    $volumeArgs += "--volume"
    $volumeArgs += "$backupDir\:/backup"

    # Fazer backup
    Write-Host "Criando backup: $backupFileName"
    try {
        $backupCmd = @("run", "--rm") + $volumeArgs + @("alpine", "tar", "czf", "/backup/$backupFileName") + ($volumes.Values | ForEach-Object { "/$_" })
        & docker @backupCmd

        if ($LASTEXITCODE -eq 0) {
            $backupPath = "$backupDir\$backupFileName"
            $backupSize = [math]::Round((Get-Item $backupPath).Length / 1MB, 2)
            Write-Host "Backup concluído com sucesso!"
            Write-Host "Arquivo: $backupPath"
            Write-Host "Tamanho: $backupSize MB"
        } else {
            throw "Comando docker falhou com código: $LASTEXITCODE"
        }
    } catch {
        Write-Error "Erro durante backup: $($_.Exception.Message)"
        Stop-Transcript
        exit 1
    }
} else {
    Write-Host "Backup pulado conforme solicitado."
}

# === 3. INICIAR SERVIÇOS ===
Write-Host "=== INICIANDO SERVIÇOS ==="

Write-Host "Iniciando containers..."
docker-compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Error "Falha ao iniciar containers"
    Stop-Transcript
    exit 1
}

# === 4. VERIFICAR SAÚDE DOS SERVIÇOS ===
Write-Host "=== VERIFICANDO SERVIÇOS ==="

# Aguardar serviços ficarem prontos
Start-Sleep -Seconds 30

# Verificar PostgreSQL
Write-Host "Verificando PostgreSQL..."
$pgCheck = docker exec n8n_postgres_db pg_isready -U n8n_user -d n8n 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ PostgreSQL está funcionando"
} else {
    Write-Warning "⚠ PostgreSQL pode não estar pronto"
}

# Verificar Redis
Write-Host "Verificando Redis..."
$redisCheck = docker exec evolution_redis redis-cli ping 2>$null
if ($redisCheck -eq "PONG") {
    Write-Host "✓ Redis está funcionando"
} else {
    Write-Warning "⚠ Redis pode não estar pronto"
}

# Verificar N8N
Write-Host "Verificando N8N (porta $n8nPort)..."
try {
    $n8nResponse = Invoke-RestMethod -Uri "http://localhost:$n8nPort" -TimeoutSec 10 -ErrorAction Stop
    Write-Host "✓ N8N está acessível"
} catch {
    Write-Warning "⚠ N8N pode não estar pronto ainda"
}

# Verificar Evolution API
Write-Host "Verificando Evolution API (porta $evolutionPort)..."
try {
    $evolutionResponse = Invoke-RestMethod -Uri "http://localhost:$evolutionPort" -TimeoutSec 10 -ErrorAction Stop
    if ($evolutionResponse.status -eq 200) {
        Write-Host "✓ Evolution API está funcionando"
        Write-Host "  Version: $($evolutionResponse.version)"
        Write-Host "  Swagger: http://localhost:$evolutionPort/docs"
        Write-Host "  Manager: http://localhost:$evolutionPort/manager"
    }
} catch {
    Write-Warning "⚠ Evolution API pode não estar pronto ainda"
}

# === 5. MOSTRAR STATUS FINAL ===
Write-Host "=== STATUS DOS CONTAINERS ==="
docker-compose ps

Write-Host ""
Write-Host "=== URLS DOS SERVIÇOS ==="
Write-Host "N8N:              http://localhost:$n8nPort"
Write-Host "Evolution API:    http://localhost:$evolutionPort"
Write-Host "Evolution Docs:   http://localhost:$evolutionPort/docs"
Write-Host "Evolution Manager: http://localhost:$evolutionPort/manager"

Write-Host ""
Write-Host "=== EXECUÇÃO CONCLUÍDA: $(Get-Date) ==="

# Limpar logs antigos (manter apenas os últimos 10 backups)
if (Test-Path $backupDir) {
    $oldBackups = Get-ChildItem -Path $backupDir -Filter "integrated_backup_*.tar.gz" |
                  Sort-Object LastWriteTime -Descending |
                  Select-Object -Skip 10

    if ($oldBackups) {
        Write-Host "Removendo $($oldBackups.Count) backup(s) antigo(s)..."
        $oldBackups | Remove-Item -Force
    }
}

Stop-Transcript
