# SCRIPT: restore-n8n.ps1

# Definir nomes dos volumes e diretório de backup
$n8nVolumeName = "n8n_n8n_data"
$postgresVolumeName = "n8n_postgres_data"
$backupDir = ".\backups"

# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# ATENÇÃO: EDITE O NOME DO ARQUIVO DE BACKUP AQUI!
# Ex: "n8n_backup_2025-09-03_13-00-00.tar"
$backupFileName = "n8n_backup_2025-09-03_01-07-00.tar"
# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

$backupFilePath = Join-Path -Path $backupDir -ChildPath $backupFileName

# --- PARTE 1: Parar os serviços e remover os volumes atuais ---
Write-Host "ATENÇÃO! ESTE SCRIPT IRÁ DELETAR OS DADOS ATUAIS DE FORMA PERMANENTE!"
Write-Host "Pressione ENTER para continuar ou CTRL+C para cancelar."
Read-Host

Write-Host "Parando e removendo containers e volumes de dados atuais..."
docker-compose down --volumes

# --- PARTE 2: Criar um container temporário para restaurar os dados ---
Write-Host "Restaurando dados do backup: $backupFileName"
try {
    # O comando 'docker run' abaixo cria um container temporário da imagem 'alpine'
    # Ele monta o arquivo de backup e os novos (e vazios) volumes de dados
    # Dentro do container, o 'tar' extrai o conteúdo do arquivo de backup para os volumes
    docker run --rm `
        --volume $n8nVolumeName:/n8n `
        --volume $postgresVolumeName:/postgres `
        --volume "$(Get-Item -Path $backupFilePath).FullName":/backup.tar `
        alpine tar -xvf /backup.tar -C /

    Write-Host "Restauração concluída com sucesso! Os volumes de dados foram restaurados."
}
catch {
    Write-Error "Ocorreu um erro durante a restauração: $($_.Exception.Message)"
}

# --- PARTE 3: Reiniciar os serviços ---
Write-Host "Reiniciando os containers do N8N e PostgreSQL..."
docker-compose up -d

Write-Host "Processo de restauração finalizado. O N8N está de volta ao ar com os dados do backup."
