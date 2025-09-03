# Definir nomes dos volumes e diretório de backup
$n8nVolumeName = "n8n_n8n_data"
$postgresVolumeName = "n8n_postgres_data"
$backupDir = ".\backups"
$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$backupFileName = "n8n_backup_$timestamp.tar"

# --- Parte 1: Parar os serviços para garantir que o backup seja consistente ---
Write-Host "Parando os containers para garantir um backup consistente..."
docker-compose down

# --- Parte 2: Criar o diretório de backups se ele não existir ---
if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir | Out-Null
    Write-Host "Diretório de backups criado em: $backupDir"
}

# --- Parte 3: Criar um container temporário para compactar os volumes ---
Write-Host "Criando backup dos volumes do N8N e PostgreSQL..."
try {
    # O comando 'docker run' abaixo cria um container temporário da imagem 'alpine'
    # Ele monta os volumes de dados e o diretório de backup
    # Dentro do container, ele usa o 'tar' para compactar os dados dos volumes para um único arquivo .tar no diretório de backup
    docker run --rm `
        --volume $n8nVolumeName:/n8n `
        --volume $postgresVolumeName:/postgres `
        --volume "$(Get-Item -Path $backupDir).FullName":/backup `
        alpine tar czvf /backup/$backupFileName -C / n8n postgres

    Write-Host "Backup concluído com sucesso! Arquivo salvo em: $backupDir\$backupFileName"
}
catch {
    Write-Error "Ocorreu um erro durante o backup: $($_.Exception.Message)"
}

# --- Parte 4: Reiniciar os serviços ---
Write-Host "Reiniciando os containers do N8N e PostgreSQL..."
docker-compose up -d

Write-Host "Processo de backup finalizado. O N8N está de volta ao ar."
