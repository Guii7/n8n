# SCRIPT: check-and-fix-volumes-fixed.ps1
# Verifica e corrige problemas com volumes Docker (CORRIGIDO para nova configuração)

param(
    [switch]$Fix = $false
)

$workingDir = "C:\Users\guii7\n8n\n8n"
Set-Location -Path $workingDir

Write-Host "=== DIAGNÓSTICO DOS VOLUMES DOCKER - CONFIGURAÇÃO ATUALIZADA ==="
Write-Host ""

# Verificar se Docker está rodando
try {
    $null = docker version 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Docker não está rodando!"
        exit 1
    }
} catch {
    Write-Error "Docker não está acessível!"
    exit 1
}

# Listar todos os volumes
Write-Host "1. VOLUMES EXISTENTES (filtro: n8n):"
docker volume ls --filter "name=n8n"

Write-Host ""
Write-Host "2. DETALHES DOS VOLUMES:"

# Volumes esperados (CORRIGIDOS para os nomes reais)
$expectedVolumes = @(
    "n8n_n8n_data",
    "n8n_postgres_data",
    "n8n_evolution_redis",      # Volume real do Redis
    "n8n_evolution_instances",  # Volume real das instâncias
    "n8n_n8n_scraper_data"     # Novo volume do N8N Scraper
)

foreach ($volume in $expectedVolumes) {
    Write-Host "   Verificando: $volume"
    $volumeInfo = docker volume inspect $volume 2>$null
    if ($LASTEXITCODE -eq 0) {
        $volumeData = $volumeInfo | ConvertFrom-Json
        $mountpoint = $volumeData.Mountpoint
        Write-Host "   ✓ Existe - Localização: $mountpoint"

        # Verificar conteúdo do volume
        $content = docker run --rm -v "${volume}:/data" alpine find /data -type f 2>$null | Measure-Object
        Write-Host "   ✓ Arquivos encontrados: $($content.Count)"
    } else {
        Write-Host "   ✗ Volume não encontrado!"
    }
    Write-Host ""
}

Write-Host "3. CONTAINERS E SEUS VOLUMES:"
docker-compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

Write-Host ""
Write-Host "4. VERIFICAÇÃO DETALHADA DOS DADOS:"

# Verificar N8N data
Write-Host "   N8N Data Volume (n8n_n8n_data):"
docker run --rm -v "n8n_n8n_data:/data" alpine ls -la /data 2>$null
if ($LASTEXITCODE -eq 0) {
    $n8nFiles = docker run --rm -v "n8n_n8n_data:/data" alpine find /data -name "*.json" -o -name "*.db*" 2>$null
    if ($n8nFiles) {
        Write-Host "   ✓ N8N tem dados (workflows, credenciais, etc.)"
        $fileCount = ($n8nFiles | Measure-Object).Count
        Write-Host "   └─ $fileCount arquivos de dados encontrados"
    } else {
        Write-Host "   ⚠ N8N volume existe mas parece vazio"
    }
} else {
    Write-Host "   ✗ Não foi possível acessar volume N8N"
}

Write-Host ""
Write-Host "   PostgreSQL Data Volume (n8n_postgres_data):"
docker run --rm -v "n8n_postgres_data:/data" alpine ls -la /data 2>$null
if ($LASTEXITCODE -eq 0) {
    $pgFiles = docker run --rm -v "n8n_postgres_data:/data" alpine find /data -name "*.conf" -o -name "base" -type d 2>$null
    if ($pgFiles) {
        Write-Host "   ✓ PostgreSQL tem dados"
        $pgSize = docker run --rm -v "n8n_postgres_data:/data" alpine du -sh /data 2>$null | ForEach-Object { ($_ -split '\s+')[0] }
        Write-Host "   └─ Tamanho aproximado: $pgSize"
    } else {
        Write-Host "   ⚠ PostgreSQL volume existe mas parece vazio"
    }
} else {
    Write-Host "   ✗ Não foi possível acessar volume PostgreSQL"
}

Write-Host ""
Write-Host "   Redis Data Volume (n8n_evolution_redis):"
docker run --rm -v "n8n_evolution_redis:/data" alpine ls -la /data 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✓ Redis volume acessível"
    $redisFiles = docker run --rm -v "n8n_evolution_redis:/data" alpine find /data -type f 2>$null
    if ($redisFiles) {
        $redisFileCount = ($redisFiles | Measure-Object).Count
        Write-Host "   └─ $redisFileCount arquivos de cache encontrados"
    } else {
        Write-Host "   └─ Volume vazio (normal se Redis acabou de iniciar)"
    }
} else {
    Write-Host "   ✗ Não foi possível acessar volume Redis"
}

Write-Host ""
Write-Host "   Evolution Instances Volume (n8n_evolution_instances):"
docker run --rm -v "n8n_evolution_instances:/data" alpine ls -la /data 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✓ Evolution instances volume acessível"
    $evolutionFiles = docker run --rm -v "n8n_evolution_instances:/data" alpine find /data -type f 2>$null
    if ($evolutionFiles) {
        $evolutionFileCount = ($evolutionFiles | Measure-Object).Count
        Write-Host "   └─ $evolutionFileCount arquivos de instância encontrados"
    } else {
        Write-Host "   └─ Volume vazio (normal se nenhuma instância foi criada)"
    }
} else {
    Write-Host "   ✗ Não foi possível acessar volume Evolution"
}

Write-Host ""
Write-Host "   N8N Scraper Volume (n8n_n8n_scraper_data):"
docker run --rm -v "n8n_n8n_scraper_data:/data" alpine ls -la /data 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✓ N8N Scraper volume acessível"
    $scraperFiles = docker run --rm -v "n8n_n8n_scraper_data:/data" alpine find /data -name "*.json" -o -name "*.db*" 2>$null
    if ($scraperFiles) {
        $scraperFileCount = ($scraperFiles | Measure-Object).Count
        Write-Host "   └─ $scraperFileCount arquivos de dados encontrados"
    } else {
        Write-Host "   └─ Volume vazio (normal para novo N8N Scraper)"
    }
} else {
    Write-Host "   ✗ Não foi possível acessar volume N8N Scraper"
}

Write-Host ""
Write-Host "5. VERIFICAÇÃO DE CONECTIVIDADE DOS CONTAINERS:"

# Verificar se containers conseguem acessar volumes
$containerVolumeMap = @{
    "n8n_affiliate_bot" = "n8n_n8n_data"
    "n8n_postgres_db" = "n8n_postgres_data"
    "evolution_redis" = "n8n_evolution_redis"
    "evolution_api" = "n8n_evolution_instances"
    "n8n_scraper" = "n8n_n8n_scraper_data"
}

foreach ($container in $containerVolumeMap.GetEnumerator()) {
    $containerName = $container.Key
    $volumeName = $container.Value

    # Verificar se container está rodando
    $containerStatus = docker inspect $containerName --format '{{.State.Status}}' 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   Container $containerName ($containerStatus):"
        if ($containerStatus -eq "running") {
            # Tentar acessar volume do container
            try {
                $volumeAccess = docker exec $containerName ls / 2>$null
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "   ✓ Volume $volumeName acessível pelo container"
                } else {
                    Write-Host "   ⚠ Problema de acesso ao volume $volumeName"
                }
            } catch {
                Write-Host "   ⚠ Não foi possível testar acesso ao volume"
            }
        } else {
            Write-Host "   ⚠ Container não está rodando, não é possível testar volumes"
        }
    } else {
        Write-Host "   Container ${containerName}: Não encontrado"
    }
}

if ($Fix) {
    Write-Host ""
    Write-Host "=== TENTANDO CORRIGIR PROBLEMAS ==="

    # Parar containers
    Write-Host "Parando containers..."
    docker-compose down

    # Recriar volumes se necessário
    foreach ($volume in $expectedVolumes) {
        $volumeExists = docker volume inspect $volume 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Criando volume: $volume"
            docker volume create $volume
        } else {
            Write-Host "Volume $volume já existe"
        }
    }

    # Limpar containers orfãos e imagens não utilizadas
    Write-Host "Limpando recursos Docker não utilizados..."
    try {
        docker system prune -f --volumes
        Write-Host "Limpeza concluída"
    } catch {
        Write-Warning "Erro durante limpeza, continuando..."
    }

    # Reiniciar containers
    Write-Host "Reiniciando containers..."
    docker-compose up -d

    Write-Host "Aguardando containers ficarem prontos..."
    Start-Sleep -Seconds 30

    # Verificar novamente
    Write-Host "Verificando status após correção..."
    docker-compose ps

    Write-Host ""
    Write-Host "Verificando conectividade dos serviços..."

    # Teste rápido de conectividade
    try {
        $pgTest = docker exec n8n_postgres_db pg_isready 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ PostgreSQL: Funcionando"
        } else {
            Write-Host "⚠ PostgreSQL: Pode estar inicializando"
        }
    } catch {
        Write-Host "⚠ PostgreSQL: Erro na verificação"
    }

    try {
        $redisTest = docker exec evolution_redis redis-cli ping 2>$null
        if ($redisTest -eq "PONG") {
            Write-Host "✓ Redis: Funcionando"
        } else {
            Write-Host "⚠ Redis: Pode estar inicializando"
        }
    } catch {
        Write-Host "⚠ Redis: Erro na verificação"
    }
}

Write-Host ""
Write-Host "=== DIAGNÓSTICO CONCLUÍDO ==="
Write-Host ""
Write-Host "RESUMO DOS VOLUMES ESPERADOS:"
Write-Host "- n8n_n8n_data: Dados do N8N principal (workflows, credenciais)"
Write-Host "- n8n_postgres_data: Base de dados PostgreSQL (compartilhada)"
Write-Host "- n8n_evolution_redis: Cache Redis para Evolution API"
Write-Host "- n8n_evolution_instances: Instâncias do WhatsApp (Evolution API)"
Write-Host "- n8n_n8n_scraper_data: Dados do N8N Scraper (isolado)"
Write-Host ""
Write-Host "DICAS:"
Write-Host "- Volumes vazios são normais em primeira execução"
Write-Host "- PostgreSQL e Redis podem demorar para inicializar"
Write-Host "- Execute com -Fix para tentar corrigir problemas automaticamente"
Write-Host "- Use 'docker-compose logs' para debug detalhado"
Write-Host "- Cloudflare Tunnel não usa volumes (configurado via token)"
