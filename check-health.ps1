# Script de Verificação de Saúde - Evolution API
# Bear Cave Labs - 11/11/2025

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

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  VERIFICAÇÃO DE SAÚDE - EVOLUTION API" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$API_URL = $LOCAL_EVOLUTION_URL
$API_KEY = $EVOLUTION_API_KEY

# Função para verificar serviço
function Test-Service {
    param(
        [string]$Name,
        [string]$Container
    )

    Write-Host "🔍 Verificando $Name..." -ForegroundColor Yellow -NoNewline

    $status = docker inspect -f '{{.State.Running}}' $Container 2>$null

    if ($status -eq "true") {
        Write-Host " ✅ ONLINE" -ForegroundColor Green
        return $true
    }
    else {
        Write-Host " ❌ OFFLINE" -ForegroundColor Red
        return $false
    }
}

# Função para verificar porta
function Test-Port {
    param(
        [string]$Hostname,
        [int]$Port
    )

    try {
        $connection = New-Object System.Net.Sockets.TcpClient
        $connection.Connect($Hostname, $Port)
        $connection.Close()
        return $true
    }
    catch {
        return $false
    }
}

# Verificar containers
Write-Host "📦 CONTAINERS" -ForegroundColor Cyan
Write-Host "─────────────" -ForegroundColor Cyan
$evolutionOk = Test-Service "Evolution API" "evolution_api"
$redisOk = Test-Service "Redis" "evolution_redis"
$rabbitmqOk = Test-Service "RabbitMQ" "evolution_rabbitmq"
$postgresOk = Test-Service "PostgreSQL" "n8n_postgres_db"
$n8nOk = Test-Service "N8N" "n8n_affiliate_bot"
Write-Host ""

# Verificar portas
Write-Host "🔌 PORTAS" -ForegroundColor Cyan
Write-Host "─────────" -ForegroundColor Cyan

Write-Host "🔍 Verificando porta 8080 (Evolution API)..." -ForegroundColor Yellow -NoNewline
if (Test-Port "localhost" 8080) {
    Write-Host " ✅ ABERTA" -ForegroundColor Green
    $port8080 = $true
} else {
    Write-Host " ❌ FECHADA" -ForegroundColor Red
    $port8080 = $false
}

Write-Host "🔍 Verificando porta 5432 (PostgreSQL)..." -ForegroundColor Yellow -NoNewline
if (Test-Port "localhost" 5432) {
    Write-Host " ✅ ABERTA" -ForegroundColor Green
} else {
    Write-Host " ❌ FECHADA" -ForegroundColor Red
}

Write-Host "🔍 Verificando porta 5672 (RabbitMQ)..." -ForegroundColor Yellow -NoNewline
if (Test-Port "localhost" 5672) {
    Write-Host " ✅ ABERTA" -ForegroundColor Green
} else {
    Write-Host " ❌ FECHADA" -ForegroundColor Red
}

Write-Host "🔍 Verificando porta 5678 (N8N)..." -ForegroundColor Yellow -NoNewline
if (Test-Port "localhost" 5678) {
    Write-Host " ✅ ABERTA" -ForegroundColor Green
} else {
    Write-Host " ❌ FECHADA" -ForegroundColor Red
}

Write-Host ""

# Verificar API
if ($evolutionOk -and $port8080) {
    Write-Host "🌐 API EVOLUTION" -ForegroundColor Cyan
    Write-Host "────────────────" -ForegroundColor Cyan

    Write-Host "🔍 Testando conexão com API..." -ForegroundColor Yellow -NoNewline
    try {
        $response = Invoke-RestMethod -Uri "$API_URL/instance/fetchInstances" `
            -Headers @{"apikey"=$API_KEY} `
            -Method Get `
            -TimeoutSec 5

        Write-Host " ✅ CONECTADO" -ForegroundColor Green

        if ($response) {
            Write-Host ""
            Write-Host "📊 Instâncias Encontradas:" -ForegroundColor Cyan

            $count = 0
            if ($response.PSObject.Properties.Name -contains "Count") {
                $count = $response.Count
            } else {
                $count = 1
            }

            Write-Host "   Total: $count" -ForegroundColor White

            if ($count -gt 0) {
                Write-Host ""
                Write-Host "   Nome: $($response.name)" -ForegroundColor White

                $statusColor = switch ($response.connectionStatus) {
                    "open" { "Green" }
                    "connecting" { "Yellow" }
                    "close" { "Red" }
                    default { "Gray" }
                }
                Write-Host "   Status: $($response.connectionStatus)" -ForegroundColor $statusColor
                Write-Host "   Número: $($response.number)" -ForegroundColor White
                Write-Host "   Token: $($response.token)" -ForegroundColor White

                # Mostrar mensagem baseada no status
                Write-Host ""
                if ($response.connectionStatus -eq "open") {
                    Write-Host "   🎉 WhatsApp CONECTADO e pronto para uso!" -ForegroundColor Green
                }
                elseif ($response.connectionStatus -eq "connecting") {
                    Write-Host "   ⏳ Aguardando conexão do WhatsApp" -ForegroundColor Yellow
                    Write-Host "   💡 Execute: .\connect-whatsapp.ps1" -ForegroundColor Cyan
                }
                else {
                    Write-Host "   ⚠️  WhatsApp desconectado" -ForegroundColor Red
                    Write-Host "   💡 Execute: .\connect-whatsapp.ps1" -ForegroundColor Cyan
                }
            }
        }
    }
    catch {
        Write-Host " ❌ ERRO: $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "─────────────────────────────────────────" -ForegroundColor Cyan

# Resumo final
Write-Host ""
Write-Host "📋 RESUMO DO SISTEMA" -ForegroundColor Cyan
Write-Host "────────────────────" -ForegroundColor Cyan

$totalServices = 5
$onlineServices = @($evolutionOk, $redisOk, $rabbitmqOk, $postgresOk, $n8nOk) | Where-Object { $_ -eq $true } | Measure-Object | Select-Object -ExpandProperty Count

$healthPercentage = [math]::Round(($onlineServices / $totalServices) * 100, 2)

Write-Host ("Serviços Online: {0}/{1} ({2}%)" -f $onlineServices, $totalServices, $healthPercentage) -ForegroundColor White

if ($healthPercentage -eq 100) {
    Write-Host ""
    Write-Host "✅ SISTEMA 100% SAUDÁVEL!" -ForegroundColor Green
    Write-Host "   Tudo funcionando perfeitamente." -ForegroundColor White
}
elseif ($healthPercentage -ge 80) {
    Write-Host ""
    Write-Host "⚠️  SISTEMA PARCIALMENTE OPERACIONAL" -ForegroundColor Yellow
    Write-Host "   Alguns serviços precisam de atenção." -ForegroundColor White
}
else {
    Write-Host ""
    Write-Host "❌ SISTEMA COM PROBLEMAS" -ForegroundColor Red
    Write-Host "   Vários serviços estão offline." -ForegroundColor White
}

Write-Host ""
Write-Host "─────────────────────────────────────────" -ForegroundColor Cyan
Write-Host ""

# Comandos úteis
Write-Host "💡 COMANDOS ÚTEIS" -ForegroundColor Cyan
Write-Host "─────────────────" -ForegroundColor Cyan
Write-Host "Conectar WhatsApp : .\connect-whatsapp.ps1" -ForegroundColor White
Write-Host "Ver logs          : docker logs evolution_api -f" -ForegroundColor White
Write-Host "Reiniciar         : docker restart evolution_api" -ForegroundColor White
Write-Host "Status containers : docker ps --filter name=evolution" -ForegroundColor White
Write-Host ""

# Perguntar se quer executar script de conexão
if ($evolutionOk -and $port8080) {
    Write-Host "🔗 Deseja abrir o script de conexão do WhatsApp? (S/N)" -ForegroundColor Yellow -NoNewline
    $answer = Read-Host " "

    if ($answer -eq "S" -or $answer -eq "s") {
        Write-Host ""
        Write-Host "🚀 Executando script de conexão..." -ForegroundColor Green
        & "$PSScriptRoot\connect-whatsapp.ps1"
    }
}

Write-Host ""
Write-Host "✅ Verificação concluída!" -ForegroundColor Green
Write-Host ""
