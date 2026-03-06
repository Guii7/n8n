# Este script faz backup completo dos volumes e inicia N8N + Evolution API + Cloudflare Tunnel

param(
    [switch]$SkipBackup = $false
)

Set-StrictMode -Version Latest

# Carregar configurações do arquivo .env.scripts
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$envFile = Join-Path $scriptDir ".env.scripts"

if (-not (Test-Path $envFile)) {
    Write-Error "Arquivo de configuração não encontrado: $envFile"
    Write-Error "Copie .env.scripts.example para .env.scripts e configure os valores."
    exit 1
}

# Função para carregar variáveis do arquivo .env.scripts
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^([^#=]+)=(.*)$') {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim()
        Set-Variable -Name $name -Value $value -Scope Script
    }
}

$workingDir        = $SCRIPTS_WORKING_DIR
$logPath           = "$workingDir\task_log.txt"
$backupDir         = "$workingDir\backups"
$timestamp         = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$backupFileName    = "integrated_backup_$timestamp.tar.gz"
$dockerDesktopPath = $DOCKER_DESKTOP_PATH

$volumes = @{
    "n8n_n8n_data"           = "n8n"
    "n8n_postgres_data"      = "postgres"
    "n8n_evolution_redis"    = "redis"
    "n8n_evolution_instances"= "evolution"
    "n8n_rabbitmq_data"      = "rabbitmq"
    "n8n_puppeteer_data"     = "puppeteer"
}

$localN8N          = $LOCAL_N8N_URL
$localEvolution    = $LOCAL_EVOLUTION_URL
$externalN8N       = $EXTERNAL_N8N_URL
$externalEvolution = $EXTERNAL_EVOLUTION_URL

Start-Transcript -Path $logPath -Append
Write-Host "=== INÍCIO DA EXECUÇÃO: $(Get-Date) ==="

# Verificação do diretório de trabalho
try {
    Set-Location -Path $workingDir -ErrorAction Stop
    Write-Host "Diretório de trabalho: $(Get-Location)"
} catch {
    Write-Error "Falha ao acessar diretório: $workingDir"
    Stop-Transcript
    exit 1
}

Write-Host "Verificando Docker Desktop..."
$dockerProcess = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue

if (-not $dockerProcess) {
    Write-Host "Docker Desktop não está rodando. Iniciando..."
    try {
        Start-Process -FilePath $dockerDesktopPath -WindowStyle Hidden
        Write-Host "Aguardando inicialização do Docker Desktop..."
        Start-Sleep -Seconds 30
    } catch {
        Write-Error "Falha ao iniciar Docker Desktop: $($_.Exception.Message)"
        Stop-Transcript
        exit 1
    }
} else {
    Write-Host "Docker Desktop já está em execução."
}

Write-Host "Verificando se Docker está acessível..."
$dockerReady = $false

for ($attempt=1; $attempt -le 30 -and -not $dockerReady; $attempt++) {
    Write-Host "Tentativa $attempt de 30..."
    try {
        $dockerVersion = docker version --format '{{.Server.Version}}' 2>$null
        if ($LASTEXITCODE -eq 0 -and $dockerVersion) {
            $dockerReady = $true
            Write-Host "Docker está pronto! Versão: $dockerVersion"
        }
    } catch {
        Write-Warning "Docker ainda não está pronto..."
    }

    if (-not $dockerReady) {
        Start-Sleep -Seconds 5
    }
}

if (-not $dockerReady) {
    Write-Error "Docker não ficou acessível após 30 tentativas."
    Stop-Transcript
    exit 1
}

# Seção de Backup
if (-not $SkipBackup) {
    Write-Host "=== INICIANDO BACKUP ==="
    Write-Host "Parando containers..."

    try {
        docker-compose down
        Start-Sleep -Seconds 5
    } catch {
        Write-Warning "Erro ao parar containers, continuando..."
    }

    if (-not (Test-Path $backupDir)) {
        try {
            New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
            Write-Host "Diretório de backup criado: $backupDir"
        } catch {
            Write-Error "Falha ao criar diretório de backup: $($_.Exception.Message)"
            Stop-Transcript
            exit 1
        }
    }

    $volumeArgs = @()
    foreach ($volume in $volumes.GetEnumerator()) {
        $volumeArgs += "--volume"
        $volumeArgs += "$($volume.Key):/$($volume.Value)"
    }
    $volumeArgs += "--volume"
    $volumeArgs += "$backupDir\:/backup"

    Write-Host "Criando backup: $backupFileName"
    try {
        $pathsToBackup = $volumes.Values | ForEach-Object { "/$_" }
        $backupCmd = @("run", "--rm") + $volumeArgs + @("alpine", "tar", "czf", "/backup/$backupFileName") + $pathsToBackup

        Write-Host "Executando comando docker para backup..."
        & docker @backupCmd

        if ($LASTEXITCODE -eq 0) {
            $backupPath = Join-Path $backupDir $backupFileName
            if (Test-Path $backupPath) {
                $backupSize = [math]::Round((Get-Item $backupPath).Length / 1MB, 2)
                Write-Host "Backup concluído com sucesso: $backupPath ($backupSize MB)"
            } else {
                Write-Warning "Arquivo de backup não encontrado após o comando ter sido executado com sucesso."
            }
        } else {
            # Modificado para não usar 'throw' para evitar possíveis problemas de parsing.
            Write-Error "O comando docker para o backup falhou com o código de saída: $LASTEXITCODE"
        }
    } catch {
        Write-Error "Ocorreu uma exceção durante o processo de backup: $($_.Exception.Message)"
    }
} else {
    Write-Host "Backup pulado conforme solicitado."
}

# Iniciando serviços
Write-Host "=== INICIANDO SERVIÇOS ==="
try {
    docker-compose up -d
    if ($LASTEXITCODE -ne 0) {
        # Usando Write-Error em vez de throw por consistência
        Write-Error "Falha ao executar docker-compose up."
        Stop-Transcript
        exit 1
    }
    Write-Host "Containers iniciados com sucesso!"
} catch {
    Write-Error "Erro ao iniciar containers: $($_.Exception.Message)"
    Stop-Transcript
    exit 1
}

Write-Host "=== VERIFICANDO SERVIÇOS ==="
Write-Host "Aguardando 30 segundos para os serviços estabilizarem..."
Start-Sleep -Seconds 30

# Verificação PostgreSQL
Write-Host "Verificando PostgreSQL..."
try {
    docker exec n8n_postgres_db pg_isready 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ PostgreSQL ok"
    } else {
        Write-Warning "⚠ PostgreSQL não pronto"
    }
} catch {
    Write-Warning "⚠ Erro ao verificar PostgreSQL: $($_.Exception.Message)"
}

# Verificação Redis
Write-Host "Verificando Redis..."
try {
    $redisCheck = docker exec evolution_redis redis-cli ping 2>$null
    if ($redisCheck -match "PONG") {
        Write-Host "✓ Redis ok"
    } else {
        Write-Warning "⚠ Redis não pronto"
    }
} catch {
    Write-Warning "⚠ Erro ao verificar Redis: $($_.Exception.Message)"
}

# Verificação Cloudflare Tunnel
Write-Host "Verificando Cloudflare Tunnel..."
try {
    $tunnelLogs = docker logs cloudflared_tunnel --tail 10 2>$null
    if ($tunnelLogs -match "Registered tunnel connection") {
        Write-Host "✓ Cloudflare Tunnel conectado"
        $connections = ($tunnelLogs | Select-String "Registered tunnel connection").Count
        if ($connections -gt 0) {
            Write-Host "  Conexões: $connections"
        }
    } else {
        Write-Warning "⚠ Tunnel pode não estar conectado"
    }
} catch {
    Write-Warning "⚠ Erro ao verificar Tunnel: $($_.Exception.Message)"
}

# Verificação N8N local
Write-Host "Verificando N8N local..."
try {
    Invoke-RestMethod -Uri $localN8N -TimeoutSec 10 -ErrorAction Stop | Out-Null
    Write-Host "✓ N8N local ok"
} catch {
    Write-Warning "⚠ N8N local não pronto: $($_.Exception.Message)"
}

# Verificação Evolution API local
Write-Host "Verificando Evolution API local..."
try {
    $evolutionResponse = Invoke-RestMethod -Uri $localEvolution -TimeoutSec 10 -ErrorAction Stop
    Write-Host "✓ Evolution API ok"
    if ($evolutionResponse.version) {
        Write-Host "  Version: $($evolutionResponse.version)"
    }
} catch {
    Write-Warning "⚠ Evolution API não pronta: $($_.Exception.Message)"
}

Write-Host "=== TESTANDO CONECTIVIDADE EXTERNA ==="

# Teste N8N externo
Write-Host "Testando N8N externo..."
try {
    Invoke-RestMethod -Uri $externalN8N -TimeoutSec 15 -ErrorAction Stop | Out-Null
    Write-Host "✓ N8N externo acessível"
} catch {
    if ($_.Exception.Message -match "not known|resolved") {
        Write-Warning "⚠ DNS N8N ainda propagando"
    } else {
        Write-Warning "⚠ N8N externo indisponível: $($_.Exception.Message)"
    }
}

# Teste Evolution API externa
Write-Host "Testando Evolution API externa..."
try {
    Invoke-RestMethod -Uri $externalEvolution -TimeoutSec 15 -ErrorAction Stop | Out-Null
    Write-Host "✓ Evolution externo acessível"
} catch {
    if ($_.Exception.Message -match "not known|resolved") {
        Write-Warning "⚠ DNS Evolution ainda propagando"
    } else {
        Write-Warning "⚠ Evolution externo indisponível: $($_.Exception.Message)"
    }
}

# Status dos containers
Write-Host "=== STATUS DOS CONTAINERS ==="
try {
    docker-compose ps
} catch {
    Write-Warning "Erro ao obter status"
}

Write-Host ""
Write-Host "=== URLS DOS SERVIÇOS ==="
Write-Host "LOCAIS:"
Write-Host "  N8N:               $localN8N"
Write-Host "  Evolution API:     $localEvolution"
Write-Host "  Evolution Docs:    $localEvolution/docs"
Write-Host "  Evolution Manager: $localEvolution/manager"
Write-Host ""
Write-Host "EXTERNOS:"
Write-Host "  N8N:               $externalN8N"
Write-Host "  Evolution API:     $externalEvolution"
Write-Host "  Evolution Docs:    $externalEvolution/docs"
Write-Host "  Evolution Manager: $externalEvolution/manager"

Write-Host ""
Write-Host "=== INFO TUNNEL ==="
try {
    $tunnelInfo = docker logs cloudflared_tunnel --tail 5 2>$null
    if ($tunnelInfo) {
        foreach ($line in $tunnelInfo) {
            Write-Host "  $line"
        }
    }
} catch {
    Write-Warning "Não foi possível obter logs do tunnel"
}

# Limpeza de backups antigos
if (Test-Path $backupDir) {
    try {
        $oldBackups = Get-ChildItem -Path $backupDir -Filter "integrated_backup_*.tar.gz" | Sort-Object LastWriteTime -Descending | Select-Object -Skip 10
        if ($oldBackups) {
            Write-Host "Removendo $($oldBackups.Count) backup(s) antigo(s)..."
            foreach ($backup in $oldBackups) {
                Remove-Item -Path $backup.FullName -Force
            }
        }
    } catch {
        Write-Warning "Erro ao limpar backups antigos: $($_.Exception.Message)"
    }
}

Write-Host ""
Write-Host "DICAS:"
Write-Host "- Se URLs externas falharem, aguarde propagação DNS"
Write-Host "- Use 'docker-compose logs cloudflared' para debug"
Write-Host "- Verifique Cloudflare dashboard para status"

Write-Host "=== EXECUÇÃO CONCLUÍDA: $(Get-Date) ==="
Stop-Transcript
