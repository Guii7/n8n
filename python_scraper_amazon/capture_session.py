"""
Script para capturar e salvar sessão da Amazon
Abre navegador, permite login manual e salva cookies/session data
"""
import os
import sys
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AmazonSessionCapture:
    def __init__(self):
        self.session_dir = Path(os.getenv('SESSION_DIR', './puppeteer_session'))
        self.session_file = self.session_dir / 'amazon_session.json'
        self.amazon_url = 'https://www.amazon.com.br'

        # Criar diretório se não existir
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def capture_session(self):
        """
        Abre navegador e permite login manual na Amazon
        Salva cookies e session data após login bem-sucedido
        """
        logger.info("=" * 70)
        logger.info("CAPTURA DE SESSÃO - AMAZON")
        logger.info("=" * 70)
        logger.info("")
        logger.info("📋 O que vai acontecer:")
        logger.info("   1. Um navegador Chrome será aberto na Amazon")
        logger.info("   2. Você faz login manualmente (sem pressa!)")
        logger.info("   3. Quando terminar, volta aqui e pressiona ENTER")
        logger.info("   4. O script salva seus cookies de sessão")
        logger.info("")
        logger.info("⏰ Não há timeout! Você tem todo o tempo que precisar.")
        logger.info("")
        input(">>> Pressione ENTER para abrir o navegador...")

        with sync_playwright() as p:
            # Iniciar navegador NÃO headless para permitir login manual
            browser = p.chromium.launch(
                headless=False,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage'
                ]
            )

            # Criar contexto com user agent realista
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='pt-BR',
                timezone_id='America/Sao_Paulo'
            )

            page = context.new_page()

            try:
                # Navegar para Amazon
                logger.info(f"🌐 Abrindo {self.amazon_url}...")
                page.goto(self.amazon_url, wait_until='domcontentloaded', timeout=30000)

                # Aguardar alguns segundos para página carregar
                page.wait_for_timeout(3000)

                logger.info("")
                logger.info("=" * 70)
                logger.info("✅ NAVEGADOR ABERTO!")
                logger.info("=" * 70)
                logger.info("")
                logger.info("👤 Faça login na sua conta Amazon agora...")
                logger.info("")
                logger.info("📋 INSTRUÇÕES:")
                logger.info("   1. Clique em 'Olá, faça seu login' ou 'Conta e Listas'")
                logger.info("   2. Faça login com email e senha")
                logger.info("   3. Resolva captchas se necessário")
                logger.info("   4. Confirme que está logado (veja seu nome no topo)")
                logger.info("   5. IMPORTANTE: Acesse o SiteStripe se estiver disponível")
                logger.info("")
                logger.info("⚠️  NÃO FECHE O NAVEGADOR! Deixe ele aberto.")
                logger.info("")
                logger.info("=" * 70)
                logger.info("⏳ AGUARDANDO VOCÊ FAZER O LOGIN...")
                logger.info("   Quando terminar, volte aqui e pressione ENTER")
                logger.info("   (O navegador será fechado automaticamente depois)")
                logger.info("=" * 70)
                logger.info("")

                # Aguardar confirmação manual do usuário
                input(">>> Pressione ENTER quando estiver logado (NÃO feche o navegador!)... ")

                # Salvar cookies IMEDIATAMENTE após confirmação
                logger.info("")
                logger.info("💾 Salvando cookies e session data...")

                # Pegar cookies do contexto (funciona mesmo se a página mudou)
                cookies = context.cookies()

                # Pegar storage state completo
                storage_state = context.storage_state()

                # Salvar em arquivo JSON
                from datetime import datetime
                session_data = {
                    'cookies': cookies,
                    'storage_state': storage_state,
                    'timestamp': datetime.now().isoformat()
                }

                with open(self.session_file, 'w', encoding='utf-8') as f:
                    json.dump(session_data, f, indent=2, ensure_ascii=False)

                logger.info(f"✅ Sessão salva em: {self.session_file}")

                # Verificar se tem cookies válidos
                amazon_cookies = [c for c in cookies if 'amazon' in c.get('domain', '')]
                if len(amazon_cookies) < 3:
                    logger.warning(f"⚠️  Poucos cookies capturados ({len(amazon_cookies)}). Verifique se está logado.")
                else:
                    logger.info(f"✅ {len(amazon_cookies)} cookies da Amazon capturados!")

                logger.info("")
                logger.info("=" * 70)
                logger.info("✅ CAPTURA CONCLUÍDA COM SUCESSO!")
                logger.info("=" * 70)
                logger.info("")
                logger.info("O navegador será fechado automaticamente.")
                logger.info("Use o scraper.py para começar a capturar ofertas.")

                # Aguardar 2 segundos antes de fechar
                import time
                time.sleep(2)

                return True

            except Exception as e:
                logger.error(f"❌ Erro durante captura de sessão: {e}")
                return False

            finally:
                browser.close()

    def validate_session(self):
        """
        Valida se existe uma sessão salva e se ainda está válida
        """
        if not self.session_file.exists():
            logger.warning("⚠️ Nenhuma sessão salva encontrada")
            return False

        try:
            with open(self.session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)

            # Verificar estrutura básica
            if 'cookies' not in session_data or 'storage_state' not in session_data:
                logger.warning("⚠️ Sessão salva está corrompida")
                return False

            # Verificar se tem cookies importantes
            cookies = session_data['cookies']
            important_cookies = ['session-id', 'ubid-acbbr']

            cookie_names = [c['name'] for c in cookies]
            has_important = any(name in cookie_names for name in important_cookies)

            if not has_important:
                logger.warning("⚠️ Sessão não contém cookies importantes da Amazon")
                return False

            logger.info("✅ Sessão válida encontrada")
            logger.info(f"   📅 Capturada em: {session_data.get('timestamp', 'N/A')}")
            logger.info(f"   🍪 Cookies salvos: {len(cookies)}")
            return True

        except Exception as e:
            logger.error(f"❌ Erro ao validar sessão: {e}")
            return False

    def load_session(self):
        """
        Carrega dados da sessão do arquivo
        """
        if not self.session_file.exists():
            return None

        try:
            with open(self.session_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"❌ Erro ao carregar sessão: {e}")
            return None


def main():
    """Função principal"""
    capturer = AmazonSessionCapture()

    # Verificar se já existe sessão
    if capturer.validate_session():
        logger.info("")
        recapture = input("Já existe uma sessão salva. Deseja capturar novamente? (s/n): ")
        if recapture.lower() != 's':
            logger.info("✅ Usando sessão existente")
            return

    # Capturar nova sessão
    success = capturer.capture_session()

    if success:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
