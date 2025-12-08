"""
Script para fazer login no Mercado Livre e salvar a sessão
Usado quando a sessão expira ou para configuração inicial

USO:
    python login_session.py

O navegador será aberto em modo VISÍVEL para você:
1. Inserir suas credenciais
2. Completar a autenticação de 2 fatores (2FA)
3. Após fazer login, a sessão será salva automaticamente
"""
import os
import sys
import time
from pathlib import Path

# Configurar encoding UTF-8 no Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()


def main():
    print("=" * 70)
    print("🔐 MERCADO LIVRE - LOGIN E SALVAMENTO DE SESSÃO")
    print("=" * 70)

    # Resolver caminho da sessão
    session_dir_env = os.getenv('SESSION_DIR', './puppeteer_session')
    if not os.path.isabs(session_dir_env):
        session_dir = os.path.abspath(session_dir_env)
    else:
        session_dir = session_dir_env

    print(f"\n📁 Pasta de sessão: {session_dir}")

    # Criar pasta se não existir
    os.makedirs(session_dir, exist_ok=True)

    # Credenciais
    ml_email = os.getenv('ML_EMAIL')
    ml_password = os.getenv('ML_PASSWORD')

    if not ml_email or not ml_password:
        print("\n❌ ERRO: ML_EMAIL e ML_PASSWORD devem estar definidos no .env!")
        return False

    print(f"📧 Email: {ml_email}")
    print(f"🔑 Senha: {'*' * len(ml_password)}")

    print("\n" + "=" * 70)
    print("🚀 INICIANDO NAVEGADOR EM MODO VISÍVEL")
    print("=" * 70)
    print("\n⚠️  IMPORTANTE:")
    print("   1. O navegador será aberto em modo VISÍVEL")
    print("   2. Faça login normalmente com seu email e senha")
    print("   3. Complete a autenticação 2FA (código no celular/email)")
    print("   4. Após fazer login, AGUARDE até ver a mensagem de sucesso")
    print("   5. NÃO FECHE o navegador manualmente!")
    print("\n")

    input("Pressione ENTER para iniciar o navegador...")

    try:
        with sync_playwright() as p:
            print("\n🌐 Abrindo navegador Chrome...")

            browser = p.chromium.launch_persistent_context(
                user_data_dir=session_dir,
                headless=False,  # SEMPRE visível para login
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--window-position=100,50',
                    '--window-size=1300,900',
                ],
                channel='chrome',
                viewport={'width': 1280, 'height': 850},
                ignore_https_errors=True,
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='pt-BR',
                timezone_id='America/Sao_Paulo'
            )

            page = browser.new_page()

            # Passo 1: Ir para página de login
            print("\n1️⃣ Acessando página de login...")
            page.goto('https://www.mercadolivre.com/jms/mlb/lgz/msl/login', timeout=60000)
            time.sleep(2)

            # Passo 2: Preencher email automaticamente
            print(f"2️⃣ Preenchendo email: {ml_email}")
            try:
                user_input = 'input[name="user_id"]'
                page.wait_for_selector(user_input, timeout=30000)
                page.fill(user_input, ml_email)
                time.sleep(0.5)

                # Clicar em continuar
                page.click('button[type="submit"]')
                time.sleep(2)
            except Exception as e:
                print(f"   ⚠️ Erro ao preencher email: {e}")
                print("   📝 Por favor, preencha manualmente no navegador")

            # Passo 3: Preencher senha automaticamente
            print(f"3️⃣ Preenchendo senha...")
            try:
                password_input = 'input[name="password"]'
                page.wait_for_selector(password_input, timeout=30000)
                page.fill(password_input, ml_password)
                time.sleep(0.5)

                # Clicar em entrar
                page.click('button[type="submit"]')
                print("   ✅ Senha enviada!")
            except Exception as e:
                print(f"   ⚠️ Erro ao preencher senha: {e}")
                print("   📝 Por favor, preencha manualmente no navegador")

            # Passo 4: Aguardar autenticação 2FA
            print("\n" + "=" * 70)
            print("📱 AUTENTICAÇÃO DE 2 FATORES (2FA)")
            print("=" * 70)
            print("\n⏳ Aguardando você completar a autenticação 2FA...")
            print("   - Verifique seu celular/email")
            print("   - Digite o código ou aprove a notificação")
            print("   - O script aguardará até 5 minutos")
            print("\n")

            # Loop de verificação (até 5 minutos)
            max_wait = 300  # 5 minutos
            check_interval = 5  # verificar a cada 5 segundos
            elapsed = 0
            logged_in = False

            while elapsed < max_wait:
                time.sleep(check_interval)
                elapsed += check_interval

                current_url = page.url

                # Verificar se saiu da página de login
                if '/login' not in current_url and '/security' not in current_url:
                    logged_in = True
                    print(f"\n✅ Login detectado! URL: {current_url}")
                    break

                remaining = max_wait - elapsed
                mins = remaining // 60
                secs = remaining % 60
                print(f"   ⏱️ Aguardando 2FA... (restam {mins}m {secs}s)")

            if not logged_in:
                print("\n❌ Timeout: Login não foi completado em 5 minutos")
                print("   Por favor, tente novamente")
                browser.close()
                return False

            # Passo 5: Navegar para validar sessão
            print("\n5️⃣ Validando sessão...")

            # Ir para página inicial
            page.goto('https://www.mercadolivre.com.br', timeout=60000)
            time.sleep(3)

            # Ir para área de afiliados
            print("   🔗 Acessando área de afiliados...")
            page.goto('https://www.mercadolivre.com.br/afiliados/hub', timeout=60000)
            time.sleep(3)

            current_url = page.url
            if '/login' in current_url or '/security' in current_url:
                print("\n❌ Erro: Ainda está sendo redirecionado para login")
                print("   A sessão pode não ter sido salva corretamente")
                browser.close()
                return False

            # Ir para linkbuilder
            print("   🔗 Acessando linkbuilder...")
            page.goto('https://www.mercadolivre.com.br/afiliados/linkbuilder', timeout=60000)
            time.sleep(3)

            current_url = page.url
            if '/afiliados' in current_url:
                print("\n" + "=" * 70)
                print("🎉 SUCESSO! SESSÃO SALVA COM SUCESSO!")
                print("=" * 70)
                print(f"\n📁 Sessão salva em: {session_dir}")
                print("\n✅ Agora você pode executar o scraper normalmente!")
                print("   Execute: python main.py")
                print("\n")
            else:
                print(f"\n⚠️ URL inesperada: {current_url}")
                print("   Verifique se sua conta tem acesso ao programa de afiliados")

            # Fechar navegador
            print("🔒 Fechando navegador e salvando sessão...")
            time.sleep(2)
            browser.close()

            return True

    except Exception as e:
        print(f"\n❌ Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()

    print("\n")
    if success:
        print("✅ Script finalizado com sucesso!")
    else:
        print("❌ Script finalizado com erro")

    input("\nPressione ENTER para fechar...")
