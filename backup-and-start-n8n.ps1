# SCRIPT: backup-and-start-n8n.ps1

# --- PARTE DO BACKUP (CÓDIGO DO backup-n8n.ps1) ---

# Definir nomes dos volumes e diretório de backup
$n8nVolumeName = "n8n_n8n_data"
$postgresVolumeName = "n8n_postgres_data"
$backupDir = ".\backups"
$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$backupFileName = "n8n_backup_$timestamp.tar"

# Parar os containers para garantir um backup consistente
Write-Host "Parando os containers para garantir um backup consistente..."
docker-compose down

# Criar o diretório de backups se ele não existir
if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir | Out-Null
    Write-Host "Diretório de backups criado em: $backupDir"
}

# Criar um container temporário para compactar os volumes
Write-Host "Criando backup dos volumes do N8N e PostgreSQL..."
try {
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

# --- PARTE DA INICIALIZAÇÃO (CÓDIGO DO start-n8n.ps1) ---

Write-Host "Iniciando o processo de inicialização do N8N..."
# Chama o seu script original de inicialização
. .\start-n8n.ps1
