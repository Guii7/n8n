# Porta que o N8N está expondo localmente (verifique seu docker-compose.yml)
$n8nPort = "5678"

# --- Parte 1: Iniciar Ngrok em segundo plano de forma desanexada ---

Write-Host "Verificando e encerrando processos ngrok existentes..."
Get-Process -Name "ngrok" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2 # Dá um momento para os processos encerrarem

Write-Host "Iniciando Ngrok em segundo plano..."
# Inicia o ngrok.exe como um processo desanexado do PowerShell.
# Note que agora o comando 'ngrok' é chamado diretamente, pois o alias da Microsoft Store está no PATH.
$null = Start-Process -FilePath "cmd.exe" -ArgumentList "/c start `"`" ngrok http --domain=ape-diverse-locust.ngrok-free.app $n8nPort" -NoNewWindow -ErrorAction Stop

# --- Parte 2: Obter o URL do Ngrok através da API Local ---

Write-Host "Ngrok iniciado. Aguardando a API local ficar disponível (porta 4040)..."
Start-Sleep -Seconds 5 # Espera um tempo inicial para o ngrok iniciar

Write-Host "Consultando a API local do Ngrok para obter a URL..."
$ngrokApiUrl = "http://localhost:4040/api/tunnels"
$publicUrl = $null
$maxApiAttempts = 15 # Tenta por até 15 * 2 = 30 segundos
$attempt = 0

while ($null -eq $publicUrl -and $attempt -lt $maxApiAttempts) {
    Start-Sleep -Seconds 2 # Espera 2 segundos entre as chamadas à API
    $attempt++
    Write-Host "Tentativa $attempt de $maxApiAttempts para obter URL da API do Ngrok..."

    try {
        $apiResponse = Invoke-RestMethod -Uri $ngrokApiUrl -ErrorAction SilentlyContinue
        if ($null -ne $apiResponse -and $null -ne $apiResponse.tunnels) {
            $tunnel = $apiResponse.tunnels | Where-Object { $_.proto -eq "https" } | Select-Object -ExpandProperty public_url -First 1
            if ($null -ne $tunnel) {
                $publicUrl = $tunnel
            }
        }
    } catch {
        Write-Warning "Erro ao consultar a API do Ngrok: $($_.Exception.Message)"
    }
}

if ($null -eq $publicUrl) {
    Write-Error "Não foi possível obter a URL pública do Ngrok via API. Verifique se o Ngrok está rodando."
    Read-Host "Pressione Enter para sair."
    exit 1
}

Write-Host "URL Pública do Ngrok obtida: $publicUrl"

# --- Parte 3: Definir a variável de ambiente e reiniciar Docker Compose ---

$env:N8N_PUBLIC_URL = $publicUrl
Write-Host "Variável N8N_PUBLIC_URL definida: $env:N8N_PUBLIC_URL"

Write-Host "Parando containers Docker Compose existentes..."
docker-compose down
Write-Host "Iniciando containers Docker Compose com a nova URL..."
docker-compose up -d

Write-Host "Automação concluída!"
Write-Host "Seu N8N deve estar acessível em: $publicUrl"
Read-Host "Pressione Enter para sair."
