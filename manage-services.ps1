# SCRIPT: manage-services-fixed.ps1
# Script para gerenciar N8N + Evolution API + Cloudflare Tunnel facilmente

param(
    [Parameter(Position=0)]
    [ValidateSet("start", "stop", "restart", "status", "logs", "backup", "restore", "update", "tunnel", "help")]
    [string]$Action = "status",

    [string]$Service = "all",  # all, n8n, evolution, postgres, redis, cloudflared, scraper, studio, kong, meta, rest, auth, storage, realtime, rabbitmq
    [string]$BackupFile = "",
    [switch]$Follow = $false,   # Para logs
    [switch]$External = $false  # Para testar URLs externas
)

$workingDir = "C:\Users\guii7\bear_cave_labs\n8n"
$backupDir = "$workingDir\backups"

# URLs dos serviços
$localN8N = "http://localhost:5678"
$localEvolution = "http://localhost:8080"
$localScraper = "http://localhost:5679"
$localStudio = "http://localhost:3000"
$localKong = "http://localhost:8888"
$externalN8N = "https://n8n.bearcavelabs.com.br"
$externalEvolution = "https://evolution.bearcavelabs.com.br"

# Mudar para diretório de trabalho
try {
    Set-Location -Path $workingDir
} catch {
    Write-Error "Não foi possível acessar o diretório: $workingDir"
    exit 1
}

function Show-Help {
    Write-Host @"
=== GERENCIADOR DE SERVIÇOS N8N + EVOLUTION API + SUPABASE + CLOUDFLARE TUNNEL ===

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
  tunnel    - Mostra informações específicas do Cloudflare Tunnel
  help      - Exibe esta ajuda

OPÇÕES:
  -Service    - Serviço específico: all, n8n, evolution, postgres, redis, cloudflared,
                scraper, studio, kong, meta, rest, auth, storage, realtime, rabbitmq
  -Follow     - Seguir logs em tempo real (usar com logs)
  -External   - Testar URLs externas também (usar com status)
  -BackupFile - Arquivo de backup para restaurar

EXEMPLOS:
  .\manage-services.ps1 start
  .\manage-services.ps1 status -External
  .\manage-services.ps1 logs -Service studio -Follow
  .\manage-services.ps1 logs -Service kong
  .\manage-services.ps1 tunnel
  .\manage-services.ps1 restore -BackupFile "integrated_backup_2025-01-01_12-00-00.tar.gz"

SERVIÇOS DISPONÍVEIS:
  - n8n: N8N principal (workflows)
  - evolution: Evolution API (WhatsApp)
  - postgres: PostgreSQL (banco compartilhado)
  - redis: Redis (cache Evolution)
  - rabbitmq: RabbitMQ (mensageria)
  - cloudflared: Cloudflare Tunnel
  - scraper: N8N Scraper
  - studio: Supabase Studio (UI)
  - kong: Kong API Gateway
  - meta: Supabase Postgres Meta
  - rest: PostgREST (REST API)
  - auth: Supabase Auth (GoTrue)
  - storage: Supabase Storage
  - realtime: Supabase Realtime
"@
}

function Test-DockerRunning {
    try {
        $null = docker version --format '{{.Server.Version}}' 2>$null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Start-Services {
    Write-Host "Verificando Docker..."
    if (-not (Test-DockerRunning)) {
        Write-Error "Docker não está rodando. Por favor, inicie o Docker Desktop primeiro."
        return
    }

    Write-Host "Iniciando serviços..."
    try {
        docker-compose up -d
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Serviços iniciados com sucesso!"
            Start-Sleep -Seconds 15
            Show-Status
        } else {
            Write-Error "Falha ao iniciar serviços"
        }
    } catch {
        Write-Error "Erro ao executar docker-compose: $($_.Exception.Message)"
    }
}

function Stop-Services {
    Write-Host "Parando serviços..."
    try {
        docker-compose down
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Serviços parados com sucesso!"
        } else {
            Write-Warning "Houve algum problema ao parar os serviços"
        }
    } catch {
        Write-Error "Erro ao parar serviços: $($_.Exception.Message)"
    }
}

function Restart-Services {
    Write-Host "Reiniciando serviços..."
    try {
        docker-compose restart
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Serviços reiniciados com sucesso!"
            Start-Sleep -Seconds 15
            Show-Status
        } else {
            Write-Error "Falha ao reiniciar serviços"
        }
    } catch {
        Write-Error "Erro ao reiniciar serviços: $($_.Exception.Message)"
    }
}

function Show-Status {
    Write-Host "=== STATUS DOS CONTAINERS ==="
    try {
        docker-compose ps
    } catch {
        Write-Warning "Erro ao obter status dos containers"
        return
    }

    Write-Host ""
    Write-Host "=== VERIFICAÇÃO DE SAÚDE ==="

    # Verificar PostgreSQL
    try {
        $pgCheck = docker exec n8n_postgres_db pg_isready 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ PostgreSQL: Funcionando"
        } else {
            Write-Host "✗ PostgreSQL: Não responsivo"
        }
    } catch {
        Write-Host "✗ PostgreSQL: Erro na verificação"
    }

    # Verificar Redis
    try {
        $redisCheck = docker exec evolution_redis redis-cli ping 2>$null
        if ($redisCheck -eq "PONG") {
            Write-Host "✓ Redis: Funcionando"
        } else {
            Write-Host "✗ Redis: Não responsivo"
        }
    } catch {
        Write-Host "✗ Redis: Erro na verificação"
    }

    # Verificar Cloudflare Tunnel
    try {
        $tunnelLogs = docker logs cloudflared_tunnel --tail 5 2>$null
        if ($tunnelLogs -match "Registered tunnel connection") {
            Write-Host "✓ Cloudflare Tunnel: Conectado"

            # Contar conexões ativas
            $connections = ($tunnelLogs | Select-String "Registered tunnel connection").Count
            if ($connections -gt 0) {
                Write-Host "  └─ Conexões ativas: $connections"
            }
        } else {
            Write-Host "✗ Cloudflare Tunnel: Não conectado"
        }
    } catch {
        Write-Host "✗ Cloudflare Tunnel: Erro na verificação"
    }

    Write-Host ""
    Write-Host "=== SERVIÇOS LOCAIS ==="

    # Verificar N8N
    try {
        $n8nResponse = Invoke-RestMethod -Uri $localN8N -TimeoutSec 5 -ErrorAction Stop
        Write-Host "✓ N8N: $localN8N"
    } catch {
        Write-Host "✗ N8N: Não acessível"
    }

    # Verificar Evolution API
    try {
        $evolutionResponse = Invoke-RestMethod -Uri $localEvolution -TimeoutSec 5 -ErrorAction Stop
        Write-Host "✓ Evolution API: $localEvolution"
        Write-Host "  ├─ Docs: $localEvolution/docs"
        Write-Host "  └─ Manager: $localEvolution/manager"

        if ($evolutionResponse.version) {
            Write-Host "  └─ Version: $($evolutionResponse.version)"
        }
    } catch {
        Write-Host "✗ Evolution API: Não acessível"
    }

    # Verificar N8N Scraper
    try {
        $scraperResponse = Invoke-RestMethod -Uri $localScraper -TimeoutSec 5 -ErrorAction Stop
        Write-Host "✓ N8N Scraper: $localScraper"
    } catch {
        Write-Host "✗ N8N Scraper: Não acessível"
    }

    # Verificar Supabase Studio
    try {
        $studioResponse = Invoke-RestMethod -Uri $localStudio -TimeoutSec 5 -ErrorAction Stop
        Write-Host "✓ Supabase Studio: $localStudio"
        Write-Host "  └─ Interface de gerenciamento do banco de dados"
    } catch {
        Write-Host "✗ Supabase Studio: Não acessível"
    }

    # Verificar Kong API Gateway
    try {
        $kongResponse = Invoke-RestMethod -Uri $localKong -TimeoutSec 5 -ErrorAction Stop
        Write-Host "✓ Kong (API Gateway): $localKong"
        Write-Host "  ├─ Meta API: $localKong/pg"
        Write-Host "  ├─ REST API: $localKong/rest/v1"
        Write-Host "  └─ Auth API: $localKong/auth/v1"
    } catch {
        Write-Host "✗ Kong: Não acessível"
    }

    # Verificar RabbitMQ
    try {
        $rabbitResponse = Invoke-RestMethod -Uri "http://localhost:15672" -TimeoutSec 5 -ErrorAction Stop
        Write-Host "✓ RabbitMQ Management: http://localhost:15672"
    } catch {
        Write-Host "✗ RabbitMQ Management: Não acessível (http://localhost:15672)"
    }

    # Testes externos (se solicitado)
    if ($External) {
        Write-Host ""
        Write-Host "=== SERVIÇOS EXTERNOS (via Cloudflare Tunnel) ==="
        Write-Host "NOTA: Pode falhar se DNS ainda não propagou"

        # Testar N8N externo
        try {
            $externalN8NResponse = Invoke-RestMethod -Uri $externalN8N -TimeoutSec 10 -ErrorAction Stop
            Write-Host "✓ N8N Externo: $externalN8N"
        } catch {
            if ($_.Exception.Message -match "could not be resolved|Name or service not known") {
                Write-Host "⚠ N8N Externo: DNS não propagado ($externalN8N)"
            } else {
                Write-Host "✗ N8N Externo: Não acessível ($externalN8N)"
            }
        }

        # Testar Evolution API externo
        try {
            $externalEvolutionResponse = Invoke-RestMethod -Uri $externalEvolution -TimeoutSec 10 -ErrorAction Stop
            Write-Host "✓ Evolution API Externo: $externalEvolution"
        } catch {
            if ($_.Exception.Message -match "could not be resolved|Name or service not known") {
                Write-Host "⚠ Evolution API Externo: DNS não propagado ($externalEvolution)"
            } else {
                Write-Host "✗ Evolution API Externo: Não acessível ($externalEvolution)"
            }
        }
    }
}

function Show-Logs {
    if (-not (Test-DockerRunning)) {
        Write-Error "Docker não está rodando."
        return
    }

    $containerMap = @{
        "all" = ""
        "n8n" = "n8n_affiliate_bot"
        "evolution" = "evolution_api"
        "postgres" = "n8n_postgres_db"
        "redis" = "evolution_redis"
        "cloudflared" = "cloudflared_tunnel"
        "scraper" = "n8n_scraper"
        "studio" = "supabase_studio"
        "kong" = "supabase_kong"
        "meta" = "supabase_meta"
        "rest" = "supabase_rest"
        "auth" = "supabase_auth"
        "storage" = "supabase_storage"
        "realtime" = "supabase_realtime"
        "rabbitmq" = "evolution_rabbitmq"
    }

    $container = $containerMap[$Service]

    try {
        if ($Follow) {
            if ($container) {
                Write-Host "Seguindo logs do container: $container (Pressione Ctrl+C para sair)"
                docker logs -f $container
            } else {
                Write-Host "Seguindo logs de todos os containers (Pressione Ctrl+C para sair)"
                docker-compose logs -f
            }
        } else {
            if ($container) {
                Write-Host "Últimas 50 linhas do container: $container"
                docker logs --tail 50 $container
            } else {
                Write-Host "Últimas 50 linhas de todos os containers"
                docker-compose logs --tail 50
            }
        }
    } catch {
        Write-Error "Erro ao exibir logs: $($_.Exception.Message)"
    }
}

function Show-TunnelInfo {
    Write-Host "=== INFORMAÇÕES DO CLOUDFLARE TUNNEL ==="

    if (-not (Test-DockerRunning)) {
        Write-Error "Docker não está rodando."
        return
    }

    # Status do container
    Write-Host "Status do container:"
    try {
        $containerStatus = docker inspect cloudflared_tunnel --format '{{.State.Status}}' 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  Container Status: $containerStatus"
        } else {
            Write-Host "  Container Status: Não encontrado ou não rodando"
            return
        }
    } catch {
        Write-Host "  Erro ao verificar container"
        return
    }

    # Logs recentes
    Write-Host ""
    Write-Host "Logs recentes do tunnel:"
    try {
        $tunnelLogs = docker logs cloudflared_tunnel --tail 10 2>$null
        $tunnelLogs | ForEach-Object { Write-Host "  $_" }
    } catch {
        Write-Host "  Erro ao obter logs"
    }

    # Informações de conexão
    Write-Host ""
    Write-Host "Conexões ativas:"
    try {
        $connectionLogs = docker logs cloudflared_tunnel 2>$null | Select-String "Registered tunnel connection"
        if ($connectionLogs) {
            $connectionCount = $connectionLogs.Count
            Write-Host "  Total de conexões registradas: $connectionCount"

            # Mostrar últimas 3 conexões
            $connectionLogs | Select-Object -Last 3 | ForEach-Object {
                if ($_ -match "connection=([a-f0-9-]+).*location=(\w+).*protocol=(\w+)") {
                    Write-Host "  └─ Conexão: $($matches[1].Substring(0,8))... | Local: $($matches[2]) | Protocolo: $($matches[3])"
                }
            }
        } else {
            Write-Host "  Nenhuma conexão encontrada nos logs"
        }
    } catch {
        Write-Host "  Erro ao analisar conexões"
    }

    # Configuração atual
    Write-Host ""
    Write-Host "Configuração de rotas:"
    try {
        $configLogs = docker logs cloudflared_tunnel 2>$null | Select-String "Updated to new configuration" | Select-Object -Last 1
        if ($configLogs) {
            if ($configLogs -match '"ingress":\[.*?\]') {
                Write-Host "  N8N: n8n.bearcavelabs.com.br → http://n8n:5678"
                Write-Host "  Evolution: evolution.bearcavelabs.com.br → http://evolution-api:8080"
            }
        }
    } catch {
        Write-Host "  Erro ao obter configuração"
    }

    Write-Host ""
    Write-Host "URLs dos serviços:"
    Write-Host "  N8N: $externalN8N"
    Write-Host "  Evolution API: $externalEvolution"
    Write-Host "  Evolution Docs: $externalEvolution/docs"
    Write-Host "  Evolution Manager: $externalEvolution/manager"
}

function New-Backup {
    Write-Host "Criando backup..."

    if (-not (Test-DockerRunning)) {
        Write-Error "Docker não está rodando."
        return
    }

    $timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
    $backupFileName = "integrated_backup_$timestamp.tar.gz"

    # Parar containers para backup consistente
    Write-Host "Parando containers temporariamente..."
    try {
        docker-compose down
    } catch {
        Write-Warning "Erro ao parar containers, continuando..."
    }

    # Criar diretório de backup
    if (-not (Test-Path $backupDir)) {
        try {
            New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
        } catch {
            Write-Error "Erro ao criar diretório de backup: $($_.Exception.Message)"
            return
        }
    }

    # Fazer backup (volumes atualizados - removido n8n_scraper_data, adicionado rabbitmq e puppeteer)
    try {
        docker run --rm `
            --volume n8n_n8n_data:/n8n `
            --volume n8n_postgres_data:/postgres `
            --volume n8n_evolution_redis:/redis `
            --volume n8n_evolution_instances:/evolution `
            --volume n8n_rabbitmq_data:/rabbitmq `
            --volume n8n_puppeteer_data:/puppeteer `
            --volume "${backupDir}:/backup" `
            alpine tar czf /backup/$backupFileName -C / n8n postgres redis evolution rabbitmq puppeteer

        if ($LASTEXITCODE -eq 0) {
            $backupPath = "$backupDir\$backupFileName"
            if (Test-Path $backupPath) {
                $backupSize = [math]::Round((Get-Item $backupPath).Length / 1MB, 2)
                Write-Host "Backup criado: $backupFileName ($backupSize MB)"
            } else {
                Write-Warning "Arquivo de backup não encontrado após criação"
            }
        } else {
            Write-Error "Falha na criação do backup"
        }

        # Reiniciar serviços
        Write-Host "Reiniciando serviços..."
        docker-compose up -d

    } catch {
        Write-Error "Erro no backup: $($_.Exception.Message)"
        # Tentar reiniciar mesmo com erro
        try {
            docker-compose up -d
        } catch {
            Write-Error "Erro crítico: não foi possível reiniciar os serviços"
        }
    }
}

function Restore-Backup {
    if (-not $BackupFile) {
        Write-Error "Especifique o arquivo de backup com -BackupFile"
        Write-Host "Backups disponíveis:"
        if (Test-Path $backupDir) {
            Get-ChildItem -Path $backupDir -Filter "*.tar.gz" | Select-Object Name, LastWriteTime, @{Name="Size(MB)";Expression={[math]::Round($_.Length/1MB,2)}}
        }
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
    try {
        docker-compose down
    } catch {
        Write-Warning "Erro ao parar serviços"
    }

    try {
        # Restaurar backup (volumes atualizados - removido n8n_scraper_data, adicionado rabbitmq e puppeteer)
        docker run --rm `
            --volume n8n_n8n_data:/n8n `
            --volume n8n_postgres_data:/postgres `
            --volume n8n_evolution_redis:/redis `
            --volume n8n_evolution_instances:/evolution `
            --volume n8n_rabbitmq_data:/rabbitmq `
            --volume n8n_puppeteer_data:/puppeteer `
            --volume "${backupDir}:/backup" `
            alpine sh -c "cd / && tar xzf /backup/$BackupFile"

        if ($LASTEXITCODE -eq 0) {
            Write-Host "Backup restaurado com sucesso!"
        } else {
            Write-Error "Falha na restauração do backup"
        }

        # Reiniciar serviços
        Write-Host "Iniciando serviços..."
        docker-compose up -d
        Start-Sleep -Seconds 20
        Show-Status

    } catch {
        Write-Error "Erro na restauração: $($_.Exception.Message)"
        try {
            docker-compose up -d
        } catch {
            Write-Error "Erro crítico: não foi possível reiniciar os serviços"
        }
    }
}

function Update-Images {
    Write-Host "Atualizando imagens Docker..."

    if (-not (Test-DockerRunning)) {
        Write-Error "Docker não está rodando."
        return
    }

    try {
        docker-compose down
        docker-compose pull
        docker-compose up -d

        Write-Host "Imagens atualizadas e serviços reiniciados!"
        Start-Sleep -Seconds 20
        Show-Status
    } catch {
        Write-Error "Erro durante atualização: $($_.Exception.Message)"
    }
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
    "tunnel" { Show-TunnelInfo }
    "help" { Show-Help }
    default { Show-Help }
}
