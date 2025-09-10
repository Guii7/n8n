# SCRIPT: manage-services.ps1
# Script para gerenciar N8N + Evolution API facilmente

param(
    [Parameter(Position=0)]
    [ValidateSet("start", "stop", "restart", "status", "logs", "backup", "restore", "update")]
    [string]$Action = "status",

    [string]$Service = "all",  # all, n8n, evolution, postgres, redis
    [string]$BackupFile = "",
    [switch]$Follow = $false   # Para logs
)

$workingDir = "C:\Users\guii7\n8n\n8n"
$backupDir = "$workingDir\backups"

# Mudar para diretório de trabalho
Set-Location -Path $workingDir

function Show-Help {
    Write-Host @"
=== GERENCIADOR DE SERVIÇOS N8N + EVOLUTION API ===

USO: .\manage-services.ps1 [AÇÃO] [OPÇÕES]

AÇÕES:
  start     - Inicia todos os serviços
  stop      - Para todos os serviços
  restart   - Reinicia todos os serviços
  status    - Mostra status dos serviços
  logs      - Exibe logs dos serviços
  backup    - Cria backup dos volumes
  restore   - Restaura backup (requer -BackupFile)
  update    - Atualiza imagens Docker

OPÇÕES:
  -Service  - Serviço específico: all, n8n, evolution, postgres, redis
  -Follow   - Seguir logs em tempo real (usar com logs)
  -BackupFile - Arquivo de backup para restaurar

EXEMPLOS:
  .\manage-services.ps1 start
  .\manage-services.ps1 logs -Service evolution -Follow
  .\manage-services.ps1 restore -BackupFile "integrated_backup_2025-01-01_12-00-00.tar.gz"
"@
}

function Start-Services {
    Write-Host "Iniciando serviços..."
    docker-compose up -d
    Start-Sleep -Seconds 10
    Show-Status
}

function Stop-Services {
    Write-Host "Parando serviços..."
    docker-compose down
}

function Restart-Services {
    Write-Host "Reiniciando serviços..."
    docker-compose restart
    Start-Sleep -Seconds 10
    Show-Status
}

function Show-Status {
    Write-Host "=== STATUS DOS CONTAINERS ==="
    docker-compose ps

    Write-Host ""
    Write-Host "=== VERIFICAÇÃO DE SAÚDE ==="

    # Verificar N8N
    try {
        $n8nResponse = Invoke-RestMethod -Uri "http://localhost:5678" -TimeoutSec 5
        Write-Host "✓ N8N: http://localhost:5678"
    } catch {
        Write-Host "✗ N8N: Não acessível"
    }

    # Verificar Evolution API
    try {
        $evolutionResponse = Invoke-RestMethod -Uri "http://localhost:8080" -TimeoutSec 5
        Write-Host "✓ Evolution API: http://localhost:8080"
        Write-Host "  └─ Docs: http://localhost:8080/docs"
        Write-Host "  └─ Manager: http://localhost:8080/manager"
    } catch {
        Write-Host "✗ Evolution API: Não acessível"
    }
}

function Show-Logs {
    $containerMap = @{
        "all" = ""
        "n8n" = "n8n_affiliate_bot"
        "evolution" = "evolution_api"
        "postgres" = "n8n_postgres_db"
        "redis" = "evolution_redis"
    }

    $container = $containerMap[$Service]

    if ($Follow) {
        if ($container) {
            docker logs -f $container
        } else {
            docker-compose logs -f
        }
    } else {
        if ($container) {
            docker logs --tail 50 $container
        } else {
            docker-compose logs --tail 50
        }
    }
}

function New-Backup {
    Write-Host "Criando backup..."
    $timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
    $backupFileName = "integrated_backup_$timestamp.tar.gz"

    # Para containers para backup consistente
    Write-Host "Parando containers temporariamente..."
    docker-compose down

    # Criar diretório de backup
    if (-not (Test-Path $backupDir)) {
        New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    }

    # Fazer backup
    try {
        docker run --rm `
            --volume n8n_n8n_data:/n8n `
            --volume n8n_postgres_data:/postgres `
            --volume n8n_evolution_redis:/redis `
            --volume n8n_evolution_instances:/evolution `
            --volume "${backupDir}:/backup" `
            alpine tar czf /backup/$backupFileName -C / n8n postgres redis evolution

        $backupPath = "$backupDir\$backupFileName"
        $backupSize = [math]::Round((Get-Item $backupPath).Length / 1MB, 2)
        Write-Host "Backup criado: $backupFileName ($backupSize MB)"

        # Reiniciar serviços
        Write-Host "Reiniciando serviços..."
        docker-compose up -d

    } catch {
        Write-Error "Erro no backup: $($_.Exception.Message)"
        docker-compose up -d  # Tentar reiniciar mesmo com erro
    }
}

function Restore-Backup {
    if (-not $BackupFile) {
        Write-Error "Especifique o arquivo de backup com -BackupFile"
        return
    }

    $backupPath = "$backupDir\$BackupFile"
    if (-not (Test-Path $backupPath)) {
        Write-Error "Arquivo de backup não encontrado: $backupPath"
        return
    }

    Write-Warning "ATENÇÃO: Esta operação irá SOBRESCREVER todos os dados atuais!"
    $confirm = Read-Host "Deseja continuar? (digite 'SIM' para confirmar)"

    if ($confirm -ne "SIM") {
        Write-Host "Operação cancelada."
        return
    }

    Write-Host "Restaurando backup: $BackupFile"

    # Parar serviços
    docker-compose down

    try {
        # Restaurar backup
        docker run --rm `
            --volume n8n_n8n_data:/n8n `
            --volume n8n_postgres_data:/postgres `
            --volume n8n_evolution_redis:/redis `
            --volume n8n_evolution_instances:/evolution `
            --volume "${backupDir}:/backup" `
            alpine sh -c "cd / && tar xzf /backup/$BackupFile"

        Write-Host "Backup restaurado com sucesso!"

        # Reiniciar serviços
        Write-Host "Iniciando serviços..."
        docker-compose up -d
        Start-Sleep -Seconds 15
        Show-Status

    } catch {
        Write-Error "Erro na restauração: $($_.Exception.Message)"
        docker-compose up -d
    }
}

function Update-Images {
    Write-Host "Atualizando imagens Docker..."

    docker-compose down
    docker-compose pull
    docker-compose up -d

    Write-Host "Imagens atualizadas e serviços reiniciados!"
    Start-Sleep -Seconds 15
    Show-Status
}

# === EXECUÇÃO PRINCIPAL ===
switch ($Action.ToLower()) {
    "start" { Start-Services }
    "stop" { Stop-Services }
    "restart" { Restart-Services }
    "status" { Show-Status }
    "logs" { Show-Logs }
    "backup" { New-Backup }
    "restore" { Restore-Backup }
    "update" { Update-Images }
    default { Show-Help }
}
