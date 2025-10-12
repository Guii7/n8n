# SCRIPT: quick-start.ps1
# Script simplificado para iniciar rapidamente todos os serviços

param(
    [switch]$SkipBackup = $false,
    [switch]$ShowStatus = $true,
    [switch]$OpenBrowser = $false
)

$workingDir = "C:\Users\guii7\n8n\n8n"
$dockerDesktopPath = "C:\Program Files\Docker\Docker\Docker Desktop.exe"

# Mudar para diretório
try {
    Set-Location -Path $workingDir
    Write-Host "Diretório: $(Get-Location)"
} catch {
    Write-Error "Erro ao acessar diretório: $workingDir"
    exit 1
}

Write-Host "=== QUICK START - N8N + EVOLUTION API + CLOUDFLARE TUNNEL ==="
Write-Host ""

# 1. Verificar Docker Desktop
Write-Host "1. Verificando Docker Desktop..."
$dockerProcess = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue
if ($null -eq $dockerProcess) {
    Write-Host "   Iniciando Docker Desktop..."
    try {
        Start-Process -FilePath $dockerDesktopPath -WindowStyle Hidden
        Write-Host "   Aguardando Docker ficar pronto..."

        # Aguardar Docker estar acessível
        $attempts = 0
        $maxAttempts = 24  # 2 minutos
        while ($attempts -lt $maxAttempts) {
            Start-Sleep -Seconds 5
            $attempts++
            try {
                $null = docker version --format '{{.Server.Version}}' 2>$null
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "   Docker pronto!"
                    break
                }
            } catch { }

            if ($attempts -eq $maxAttempts) {
                Write-Error "Docker não ficou pronto em tempo hábil"
                exit 1
            }
            Write-Host "   Aguardando... ($attempts/$maxAttempts)"
        }
    } catch {
        Write-Error "Erro ao iniciar Docker Desktop: $($_.Exception.Message)"
        exit 1
    }
} else {
    Write-Host "   Docker Desktop já está rodando"
}

# 2. Backup (opcional)
if (-not $SkipBackup) {
    Write-Host ""
    Write-Host "2. Fazendo backup rápido..."
    try {
        & ".\backup-and-start-services.ps1" -SkipBackup:$false
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Backup falhou, mas continuando..."
        }
    } catch {
        Write-Warning "Erro no backup, mas continuando: $($_.Exception.Message)"
    }
} else {
    Write-Host ""
    Write-Host "2. Backup pulado"

    # 3. Iniciar serviços diretamente
    Write-Host ""
    Write-Host "3. Iniciando serviços..."
    try {
        docker-compose up -d
        if ($LASTEXITCODE -eq 0) {
            Write-Host "   Serviços iniciados com sucesso!"
        } else {
            Write-Error "Falha ao iniciar serviços"
            exit 1
        }
    } catch {
        Write-Error "Erro ao iniciar serviços: $($_.Exception.Message)"
        exit 1
    }
}

# 4. Aguardar inicialização
Write-Host ""
Write-Host "4. Aguardando inicialização completa..."
$dots = ""
for ($i = 1; $i -le 30; $i++) {
    $dots += "."
    Write-Host "`r   Aguardando$dots" -NoNewline
    Start-Sleep -Seconds 1
}
Write-Host ""

# 5. Verificar status
if ($ShowStatus) {
    Write-Host ""
    Write-Host "5. Verificando status dos serviços..."

    # Status dos containers
    Write-Host ""
    Write-Host "   Containers:"
    docker-compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

    Write-Host ""
    Write-Host "   Saúde dos serviços:"

    # PostgreSQL
    try {
        $pgCheck = docker exec n8n_postgres_db pg_isready 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "   ✓ PostgreSQL: OK"
        } else {
            Write-Host "   ⚠ PostgreSQL: Iniciando..."
        }
    } catch {
        Write-Host "   ✗ PostgreSQL: Erro"
    }

    # Redis
    try {
        $redisCheck = docker exec evolution_redis redis-cli ping 2>$null
        if ($redisCheck -eq "PONG") {
            Write-Host "   ✓ Redis: OK"
        } else {
            Write-Host "   ⚠ Redis: Iniciando..."
        }
    } catch {
        Write-Host "   ✗ Redis: Erro"
    }

    # Cloudflare Tunnel
    try {
        $tunnelLogs = docker logs cloudflared_tunnel --tail 5 2>$null
        if ($tunnelLogs -match "Registered tunnel connection") {
            $connections = ($tunnelLogs | Select-String "Registered tunnel connection").Count
            Write-Host "   ✓ Cloudflare Tunnel: Conectado ($connections conexões)"
        } else {
            Write-Host "   ⚠ Cloudflare Tunnel: Conectando..."
        }
    } catch {
        Write-Host "   ✗ Cloudflare Tunnel: Erro"
    }

    # N8N
    try {
        $n8nResponse = Invoke-RestMethod -Uri "http://localhost:5678" -TimeoutSec 8 -ErrorAction Stop
        Write-Host "   ✓ N8N: Acessível (http://localhost:5678)"
    } catch {
        Write-Host "   ⚠ N8N: Iniciando... (http://localhost:5678)"
    }

    # Evolution API
    try {
        $evolutionResponse = Invoke-RestMethod -Uri "http://localhost:8080" -TimeoutSec 8 -ErrorAction Stop
        Write-Host "   ✓ Evolution API: Acessível (http://localhost:8080)"
        if ($evolutionResponse.version) {
            Write-Host "     Version: $($evolutionResponse.version)"
        }
    } catch {
        Write-Host "   ⚠ Evolution API: Iniciando... (http://localhost:8080)"
    }

    # N8N Scraper
    try {
        $scraperResponse = Invoke-RestMethod -Uri "http://localhost:5679" -TimeoutSec 8 -ErrorAction Stop
        Write-Host "   ✓ N8N Scraper: Acessível (http://localhost:5679)"
    } catch {
        Write-Host "   ⚠ N8N Scraper: Iniciando... (http://localhost:5679)"
    }
}

# 6. URLs finais
Write-Host ""
Write-Host "=== SERVIÇOS DISPONÍVEIS ==="
Write-Host ""
Write-Host "LOCAIS:"
Write-Host "  • N8N Principal:      http://localhost:5678"
Write-Host "  • Evolution API:      http://localhost:8080"
Write-Host "    ├─ Swagger Docs:    http://localhost:8080/docs"
Write-Host "    └─ Manager:         http://localhost:8080/manager"
Write-Host "  • N8N Scraper:        http://localhost:5679"
Write-Host ""
Write-Host "EXTERNOS (após propagação DNS):"
Write-Host "  • N8N Principal:      https://n8n.bearcavelabs.com.br"
Write-Host "  • Evolution API:      https://evolution.bearcavelabs.com.br"
Write-Host "    ├─ Swagger Docs:    https://evolution.bearcavelabs.com.br/docs"
Write-Host "    └─ Manager:         https://evolution.bearcavelabs.com.br/manager"

# 7. Abrir browser (opcional)
if ($OpenBrowser) {
    Write-Host ""
    Write-Host "7. Abrindo serviços no navegador..."
    try {
        Start-Process "http://localhost:5678"        # N8N
        Start-Sleep -Seconds 2
        Start-Process "http://localhost:8080/docs"   # Evolution API Docs
        Start-Sleep -Seconds 2
        Start-Process "http://localhost:5679"        # N8N Scraper
    } catch {
        Write-Warning "Erro ao abrir navegador: $($_.Exception.Message)"
    }
}

Write-Host ""
Write-Host "=== INICIALIZAÇÃO CONCLUÍDA ==="
Write-Host ""
Write-Host "COMANDOS ÚTEIS:"
Write-Host "  Status:    .\manage-services.ps1 status"
Write-Host "  Logs:      .\manage-services.ps1 logs -Follow"
Write-Host "  Tunnel:    .\manage-services.ps1 tunnel"
Write-Host "  Parar:     .\manage-services.ps1 stop"
Write-Host "  Backup:    .\manage-services.ps1 backup"
Write-Host ""
Write-Host "NOTAS:"
Write-Host "• Se serviços não estão acessíveis ainda, aguarde mais alguns minutos"
Write-Host "• URLs externos podem demorar até 48h para funcionar (propagação DNS)"
Write-Host "• Use Ctrl+C para interromper logs em tempo real"
Write-Host "• Cloudflare Tunnel funciona automaticamente, sem necessidade de intervenção"
Write-Host ""
Write-Host "Tudo pronto para uso! 🚀"
