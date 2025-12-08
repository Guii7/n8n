"""
Gerador de links afiliados do Mercado Livre usando Playwright
Usa sessão persistente do Windows para evitar login repetido
Refatorado v2: Melhor tratamento de erros, retry logic e session management
"""
import os
import time
import logging
import sys
import signal
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from dotenv import load_dotenv

load_dotenv()

# Obter logger (herdará configuração de main.py)
logger = logging.getLogger(__name__)


class AffiliateLinkGenerator:
    def __init__(self, force_visible=False):
        """
        Args:
            force_visible (bool): Se True, força modo visível independente do .env
        """
        self.linkbuilder_url = "https://www.mercadolivre.com.br/afiliados/linkbuilder"

        # Resolver caminho da sessão (deve ser absoluto)
        session_dir_env = os.getenv('SESSION_DIR', './puppeteer_session')
        if not os.path.isabs(session_dir_env):
            self.session_dir = os.path.abspath(session_dir_env)
        else:
            self.session_dir = session_dir_env

        logger.info(f"📁 Sessão Playwright: {self.session_dir}")

        # Validar que a pasta existe
        if not os.path.exists(self.session_dir):
            logger.warning(f"⚠️ Pasta de sessão não existe. Será criada automaticamente: {self.session_dir}")
            os.makedirs(self.session_dir, exist_ok=True)

        # Modo headless
        if force_visible:
            self.headless = False
        else:
            self.headless = os.getenv('HEADLESS', 'False').lower() == 'true'

        # Modo janela oculta (não interfere com clipboard/input do sistema)
        self.browser_window_hidden = os.getenv('BROWSER_WINDOW_HIDDEN', 'True').lower() == 'true'

        logger.info(f"🎬 Modo headless: {self.headless}")
        logger.info(f"🪟 Janela oculta: {self.browser_window_hidden}")

        # Credenciais
        self.ml_email = os.getenv('ML_EMAIL')
        self.ml_password = os.getenv('ML_PASSWORD')

        if not self.ml_email or not self.ml_password:
            logger.error("❌ ML_EMAIL e ML_PASSWORD devem estar definidos no .env!")
            raise ValueError("Credenciais do Mercado Livre não configuradas")

        # Configurações de timeout e retry
        self.max_batch_size = 30
        self.max_retries = 3
        self.timeout_ms = 45000  # 45 segundos (aumentado de 30s)
        self.navigation_timeout_ms = 60000  # 60 segundos para navegação

        # Configurações de otimização (carregadas do .env)
        try:
            self.links_per_batch = int(os.getenv('LINKS_PER_BATCH', '8'))
            if self.links_per_batch < 1 or self.links_per_batch > 20:
                logger.warning(f"⚠️ LINKS_PER_BATCH={self.links_per_batch} inválido, usando 8")
                self.links_per_batch = 8
        except ValueError:
            logger.warning("⚠️ LINKS_PER_BATCH não é um número, usando 8")
            self.links_per_batch = 8

        try:
            self.link_generation_wait_time = float(os.getenv('LINK_GENERATION_WAIT_TIME', '2'))
            if self.link_generation_wait_time < 0.5 or self.link_generation_wait_time > 10:
                logger.warning(f"⚠️ LINK_GENERATION_WAIT_TIME={self.link_generation_wait_time} inválido, usando 2")
                self.link_generation_wait_time = 2
        except ValueError:
            logger.warning("⚠️ LINK_GENERATION_WAIT_TIME não é um número, usando 2")
            self.link_generation_wait_time = 2

        logger.info(f"⏱️ Timeout: {self.timeout_ms}ms | Max retries: {self.max_retries}")
        logger.info(f"🔄 Links per batch: {self.links_per_batch} | Wait time: {self.link_generation_wait_time}s")

    def _launch_browser(self):
        """
        Lança browser com sessão persistente de forma segura

        Returns:
            Playwright BrowserContext
        """
        try:
            p = sync_playwright().start()

            browser_args = [
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--start-minimized',
            ]

            # Se janela oculta está ativa, posiciona fora da tela
            if self.browser_window_hidden:
                browser_args.append('--window-position=-2400,-2400')
                logger.info("🪟 Navegador rodará oculto (não interfere com seu clipboard/input)")
            else:
                logger.info("🪟 Navegador será visível (atenção: pode interferir com clipboard)")

            logger.info("🚀 Iniciando Playwright com Chrome...")

            browser = p.chromium.launch_persistent_context(
                user_data_dir=self.session_dir,
                headless=self.headless,
                args=browser_args,
                channel='chrome',
                viewport={'width': 1280, 'height': 720},
                ignore_https_errors=True,
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='pt-BR',
                timezone_id='America/Sao_Paulo'
            )

            logger.info("✅ Browser iniciado com sucesso")
            return p, browser

        except Exception as e:
            logger.error(f"❌ Erro ao iniciar browser: {e}")
            raise

    def _verify_session(self, page, attempt=1):
        """
        Verifica se a sessão está válida (logada e com acesso aos afiliados)

        Args:
            page: Página do Playwright
            attempt: Número da tentativa

        Returns:
            bool: True se sessão é válida
        """
        try:
            logger.info(f"🔍 Verificando sessão (tentativa {attempt}/{self.max_retries})...")

            # Tenta acessar página autenticada
            page.goto('https://www.mercadolivre.com.br/compras', timeout=self.timeout_ms, wait_until='domcontentloaded')
            time.sleep(1)

            current_url = page.url
            logger.info(f"📍 URL atual: {current_url}")

            # Se foi redirecionado para login, sessão é inválida
            if '/login' in current_url or '/security' in current_url:
                logger.warning("⚠️ Sessão inválida - redirecionado para login")
                # Limpa a sessão para forçar re-login na próxima tentativa
                self._cleanup_session()
                return False

            logger.info("✅ Sessão válida!")
            return True

        except PlaywrightTimeoutError:
            logger.error(f"⏱️ Timeout ao verificar sessão: {PlaywrightTimeoutError}")
            return False
        except Exception as e:
            logger.error(f"❌ Erro ao verificar sessão: {e}")
            return False

    def _warm_up_session(self, page):
        """
        Aquece a sessão navegando de forma natural por varias páginas
        Isso evita que Mercado Livre nos redirecione para login ao acessar linkbuilder

        Fluxo: Home → Ofertas → Home → Affiliate Hub → LinkBuilder

        Args:
            page: Página do Playwright

        Returns:
            bool: True se conseguiu completar o fluxo
        """
        try:
            logger.info("🔥 Aquecendo sessão com navegação natural...")

            # PASSO 1: Página inicial
            logger.info("1️⃣ Acessando página inicial: https://www.mercadolivre.com.br")
            page.goto('https://www.mercadolivre.com.br', timeout=self.navigation_timeout_ms, wait_until='domcontentloaded')
            time.sleep(5)  # 5 segundos entre navegações
            logger.info(f"   📍 Atual: {page.url}")

            # PASSO 2: Página de ofertas
            logger.info("2️⃣ Acessando página de ofertas: https://www.mercadolivre.com.br/ofertas")
            page.goto('https://www.mercadolivre.com.br/ofertas#nav-header', timeout=self.navigation_timeout_ms, wait_until='domcontentloaded')
            time.sleep(5)  # 5 segundos entre navegações
            logger.info(f"   📍 Atual: {page.url}")

            # PASSO 3: Voltar para página inicial
            logger.info("3️⃣ Voltando à página inicial: https://www.mercadolivre.com.br")
            page.goto('https://www.mercadolivre.com.br', timeout=self.navigation_timeout_ms, wait_until='domcontentloaded')
            time.sleep(5)  # 5 segundos entre navegações
            logger.info(f"   📍 Atual: {page.url}")

            # PASSO 4: Central de afiliados
            logger.info("4️⃣ Acessando Central de Afiliados: https://www.mercadolivre.com.br/afiliados/hub")
            page.goto('https://www.mercadolivre.com.br/afiliados/hub#menu-user', timeout=self.navigation_timeout_ms, wait_until='domcontentloaded')
            time.sleep(5)  # 5 segundos entre navegações
            current_url = page.url
            logger.info(f"   📍 Atual: {current_url}")

            # Verifica redirecionamento
            if '/login' in current_url or '/security' in current_url:
                logger.error("❌ Redirecionado para login na Central de Afiliados")
                return False

            if '/afiliados' not in current_url and 'hub' not in current_url:
                logger.warning(f"⚠️ URL não é a esperada: {current_url} (continuando mesmo assim...)")

            logger.info("✅ Sessão aquecida com sucesso!")
            return True

        except PlaywrightTimeoutError:
            logger.error("❌ Timeout ao aquecer sessão")
            return False
        except Exception as e:
            logger.error(f"❌ Erro ao aquecer sessão: {e}")
            return False

    def _verify_linkbuilder_access(self, page):
        """
        Verifica se consegue acessar a página de linkbuilder

        IMPORTANTE: Deve ser chamado APÓS _warm_up_session()

        Args:
            page: Página do Playwright

        Returns:
            bool: True se consegue acessar linkbuilder
        """
        try:
            logger.info("🔗 Verificando acesso ao Linkbuilder...")

            page.goto(self.linkbuilder_url, timeout=self.navigation_timeout_ms, wait_until='domcontentloaded')
            time.sleep(2)

            current_url = page.url
            logger.info(f"📍 URL atual: {current_url}")

            # Verificar redirecionamento para login
            if '/login' in current_url or '/security' in current_url:
                logger.error("❌ Redirecionado para login - Conta não aprovada no programa de afiliados?")
                # Limpa a sessão para forçar re-login
                self._cleanup_session()
                return False

            # Verificar se está na página de afiliados
            if '/afiliados' not in current_url:
                logger.error(f"❌ URL inesperada: {current_url}")
                return False

            logger.info("✅ Linkbuilder acessível!")
            return True

        except PlaywrightTimeoutError:
            logger.error(f"⏱️ Timeout ao acessar linkbuilder")
            return False
        except Exception as e:
            logger.error(f"❌ Erro ao verificar linkbuilder: {e}")
            return False

    def _cleanup_session(self):
        """
        Limpa a sessão Playwright para forçar nova autenticação
        Útil quando cookies expiram ou sessão é invalidada
        """
        try:
            import shutil

            session_default = os.path.join(self.session_dir, 'Default')

            if os.path.exists(session_default):
                logger.warning(f"🧹 Limpando cookies expirados em {session_default}...")

                # Remove apenas os arquivos de cookies, mantém outras configurações
                cookies_files = ['Cookies', 'Extension Cookies', 'Extension Cookies-journal']

                for fname in cookies_files:
                    fpath = os.path.join(session_default, fname)
                    if os.path.exists(fpath):
                        try:
                            os.remove(fpath)
                            logger.info(f"  ✅ Removido: {fname}")
                        except Exception as e:
                            logger.warning(f"  ⚠️ Erro ao remover {fname}: {e}")

                logger.info("🧹 Limpeza concluída - próxima execução fará novo login")

        except Exception as e:
            logger.error(f"❌ Erro ao limpar sessão: {e}")


    def _do_login(self, page, attempt=1):
        """
        Faz login no Mercado Livre seguindo fluxo natural

        Args:
            page: Página do Playwright
            attempt: Número da tentativa

        Returns:
            bool: True se login bem-sucedido
        """
        try:
            logger.info(f"🔐 Iniciando login (tentativa {attempt}/{self.max_retries})...")

            # Vai para página inicial
            logger.info("📌 Acessando página inicial...")
            page.goto('https://www.mercadolivre.com.br', timeout=self.timeout_ms)
            time.sleep(1)

            # Vai para página de login
            logger.info("📌 Acessando página de login...")
            page.goto('https://www.mercadolivre.com/jms/mlb/lgz/msl/login', timeout=self.timeout_ms)
            time.sleep(2)

            # Digita email
            logger.info(f"📧 Digitando email: {self.ml_email}")
            try:
                user_input = 'input[name="user_id"]'
                page.wait_for_selector(user_input, timeout=self.timeout_ms)
                page.fill(user_input, self.ml_email)
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"❌ Erro ao digitar email: {e}")
                return False

            # Clica em continuar
            logger.info("👆 Clicando em 'Continuar'...")
            try:
                page.click('button[type="submit"]')
                page.wait_for_load_state('domcontentloaded', timeout=self.timeout_ms)
                time.sleep(2)
            except Exception as e:
                logger.error(f"❌ Erro ao clicar em continuar: {e}")
                return False

            # Digita senha
            logger.info("🔑 Digitando senha...")
            try:
                password_input = 'input[name="password"]'
                page.wait_for_selector(password_input, timeout=self.timeout_ms)
                page.fill(password_input, self.ml_password)
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"❌ Erro ao digitar senha: {e}")
                return False

            # Clica em entrar
            logger.info("👆 Clicando em 'Entrar'...")
            try:
                page.click('button[type="submit"]')
            except Exception as e:
                logger.error(f"❌ Erro ao clicar em entrar: {e}")
                return False

            # Aguarda 2FA (até 120 segundos)
            logger.info("⏳ Aguardando 2FA (até 2 minutos)...")
            logger.info("📱 Complete a autenticação no seu celular/email!")

            try:
                page.wait_for_load_state('domcontentloaded', timeout=120000)
                time.sleep(3)
            except PlaywrightTimeoutError:
                logger.warning("⚠️ Timeout de 2FA (página ainda carregando)")

            final_url = page.url
            logger.info(f"📍 URL final: {final_url}")

            # Verifica se ainda está em login
            if '/login' in final_url or '/security' in final_url:
                logger.error("❌ Login não completado - ainda em página de login")
                return False

            logger.info("✅ Login bem-sucedido!")
            return True

        except Exception as e:
            logger.error(f"❌ Erro durante login: {e}")
            return False

    def generate_batch(self, product_urls):
        """
        Gera links afiliados para múltiplos produtos (até 30 por vez).

        Args:
            product_urls (list): Lista de URLs de produtos

        Returns:
            dict: Mapa {url_original: link_afiliado}
        """
        results = {}
        total = len(product_urls)

        if total == 0:
            logger.warning("⚠️ Lista de URLs vazia!")
            return results

        logger.info(f"\n🔄 Gerando {total} links afiliados em lote...")
        logger.info(f"📦 Tamanho do lote: até {self.max_batch_size} URLs por requisição")

        # Divide em chunks
        for i in range(0, total, self.max_batch_size):
            chunk = product_urls[i:i + self.max_batch_size]
            chunk_num = (i // self.max_batch_size) + 1
            total_chunks = (total + self.max_batch_size - 1) // self.max_batch_size

            logger.info(f"\n📋 Lote {chunk_num}/{total_chunks}: {len(chunk)} URLs")

            # NOVIDADE: Executar com timeout máximo de 120 segundos
            chunk_results = self._generate_batch_chunk_with_timeout(chunk, timeout_seconds=120)

            # Adiciona aos resultados
            results.update(chunk_results)

            # Delay entre lotes (evita rate limit)
            if i + self.max_batch_size < total:
                logger.info(f"⏳ Aguardando 3s antes do próximo lote...")
                time.sleep(3)

        success = len(results)
        percentage = (success * 100) // total if total > 0 else 0
        logger.info(f"\n✅ Resultado: {success}/{total} links ({percentage}%)")

        return results

    def _generate_batch_chunk_with_timeout(self, product_urls, timeout_seconds=120):
        """
        Executa _generate_batch_chunk com timeout máximo.
        Se ultrapassar o timeout, retorna resultado vazio (vai fazer retry)

        Args:
            product_urls: Lista de URLs
            timeout_seconds: Tempo máximo em segundos

        Returns:
            dict: Resultado (vazio se timed out)
        """
        result_container = {}
        exception_container = []

        def chunk_worker():
            try:
                chunk_result = self._generate_batch_chunk(product_urls)
                result_container['result'] = chunk_result
            except Exception as e:
                exception_container.append(e)

        logger.info(f"   ⏱️ Timeout máximo para este lote: {timeout_seconds}s")

        # Executar em thread com timeout
        thread = threading.Thread(target=chunk_worker, daemon=True)
        thread.start()
        thread.join(timeout=timeout_seconds)

        if thread.is_alive():
            logger.error(f"   ⏱️ ❌ TIMEOUT! Lote demorou mais de {timeout_seconds}s - marcando para retry")
            return {}  # Retorna vazio para fazer retry

        if exception_container:
            logger.error(f"   ❌ Erro na thread: {exception_container[0]}")
            return {}

        return result_container.get('result', {})


    def _generate_batch_chunk(self, product_urls):
        """
        Gera links para um chunk de URLs com retry logic

        Args:
            product_urls (list): Lista de URLs (máximo 30)

        Returns:
            dict: Mapa {url_original: link_afiliado}
        """
        if len(product_urls) > self.max_batch_size:
            logger.warning(f"⚠️ Chunk muito grande ({len(product_urls)}), limitando a {self.max_batch_size}")
            product_urls = product_urls[:self.max_batch_size]

        # Retry loop
        for attempt in range(1, self.max_retries + 1):
            logger.info(f"\n🔄 Tentativa {attempt}/{self.max_retries} para este lote")

            p = None
            browser = None

            try:
                # Se não é a primeira tentativa, limpa a sessão (pode estar expirada)
                if attempt > 1:
                    logger.info("🔄 Limpando sessão antiga antes de tentar novamente...")
                    self._cleanup_session()
                    time.sleep(1)

                p, browser = self._launch_browser()

                # Pega página existente ou cria nova
                page = browser.pages[0] if browser.pages else browser.new_page()

                # Verifica sessão
                session_valid = self._verify_session(page, attempt)

                if not session_valid:
                    logger.warning("⚠️ Sessão não está válida, tentando fazer login...")
                    # Tenta fazer login
                    login_success = self._do_login(page, attempt)

                    if not login_success:
                        logger.error("❌ Login falhou - pode ser que a conta não esteja configurada")
                        if browser:
                            browser.close()
                        if p:
                            p.stop()

                        if attempt < self.max_retries:
                            wait_time = 2 * attempt
                            logger.info(f"⏳ Aguardando {wait_time}s antes da próxima tentativa...")
                            time.sleep(wait_time)
                            continue
                        else:
                            logger.error("❌ Todas as tentativas de login falharam")
                            return {}

                # Após login bem-sucedido, aquece a sessão navegando naturalmente
                logger.info("\n🔄 Etapa 2: Navegação Natural (aquecer sessão)")
                warmup_success = self._warm_up_session(page)

                if not warmup_success:
                    logger.error("❌ Falha ao aquecer sessão")
                    if browser:
                        browser.close()
                    if p:
                        p.stop()

                    if attempt < self.max_retries:
                        wait_time = 2 * attempt
                        logger.info(f"⏳ Aguardando {wait_time}s antes da próxima tentativa...")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error("❌ Não conseguiu aquecer sessão após múltiplas tentativas")
                        return {}

                # Agora verifica acesso ao linkbuilder (após aquecimento)
                logger.info("\n🔄 Etapa 3: Verificando Acesso ao LinkBuilder")
                linkbuilder_access = self._verify_linkbuilder_access(page)

                if not linkbuilder_access:
                    logger.error("❌ Sem acesso ao Linkbuilder")
                    if browser:
                        browser.close()
                    if p:
                        p.stop()

                    if attempt < self.max_retries:
                        wait_time = 2 * attempt
                        logger.info(f"⏳ Aguardando {wait_time}s antes da próxima tentativa...")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error("❌ Não conseguiu acessar linkbuilder após múltiplas tentativas")
                        return {}

                # Processa as URLs
                logger.info(f"📝 Processando {len(product_urls)} URLs...")
                chunk_results = self._process_urls_on_page(page, product_urls)

                if browser:
                    browser.close()
                if p:
                    p.stop()

                return chunk_results

            except Exception as e:
                error_msg = str(e).lower()
                logger.error(f"❌ Erro na tentativa {attempt}: {e}")

                # ERRO CRÍTICO: Sync API inside asyncio loop - não fazer retry
                if "sync api inside the asyncio loop" in error_msg or "asyncio" in error_msg:
                    logger.error("⚠️ ERRO CRÍTICO: Sync API com asyncio event loop - não é possível fazer retry no mesmo processo")
                    logger.error("💡 Solução: Reiniciar o aplicação ou renovar a sessão via script de login")
                    if browser:
                        try:
                            browser.close()
                        except:
                            pass
                    if p:
                        try:
                            p.stop()
                        except:
                            pass
                    return {}

                if browser:
                    try:
                        browser.close()
                    except:
                        pass
                if p:
                    try:
                        p.stop()
                    except:
                        pass

                if attempt < self.max_retries:
                    wait_time = 2 * attempt  # Backoff exponencial
                    logger.info(f"⏳ Aguardando {wait_time}s antes da próxima tentativa...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"❌ Falha após {self.max_retries} tentativas")
                    return {}

        return {}

    def _process_urls_on_page(self, page, product_urls):
        """
        Processa as URLs na página de linkbuilder - OTIMIZADO para múltiplas URLs por vez

        O Mercado Livre permite enviar múltiplas URLs de uma vez (separadas por quebra de linha)
        e retorna todos os links de afiliados simultaneamente. Isso é MUITO mais rápido.

        Args:
            page: Página do Playwright
            product_urls: Lista de URLs para processar

        Returns:
            dict: Mapa {url_original: link_afiliado}
        """
        results = {}

        try:
            # Busca a textarea de input
            textarea_selector = 'textarea.andes-form-control__field'

            # Processa URLs em grupos (usando configuração do .env)
            urls_per_batch = self.links_per_batch
            total_batches = (len(product_urls) + urls_per_batch - 1) // urls_per_batch

            logger.info(f"📊 Processando {len(product_urls)} URLs em {total_batches} sub-lotes ({urls_per_batch} URLs por sub-lote)")

            for batch_idx in range(0, len(product_urls), urls_per_batch):
                batch_urls = product_urls[batch_idx:batch_idx + urls_per_batch]
                batch_num = (batch_idx // urls_per_batch) + 1

                logger.info(f"\n   � Sub-lote {batch_num}/{total_batches}: {len(batch_urls)} URLs")

                try:
                    # Preenche a textarea com MÚLTIPLAS URLs (separadas por quebra de linha)
                    page.wait_for_selector(textarea_selector, timeout=self.timeout_ms)
                    urls_text = '\n'.join(batch_urls)

                    # Limpa antes de preencher
                    page.fill(textarea_selector, '')
                    time.sleep(0.3)

                    # Preenche com todas as URLs
                    page.fill(textarea_selector, urls_text)
                    time.sleep(0.5)

                    # Clica no botão gerar UMA VEZ para todas as URLs
                    generate_button = 'button.andes-button--loud'
                    page.click(generate_button)

                    # Aguarda geração dos links (quanto mais URLs, mais tempo)
                    # Cálculo: tempo_base (do .env) + 0.3s por URL adicional
                    wait_time = self.link_generation_wait_time + (len(batch_urls) * 0.3)
                    logger.info(f"      ⏳ Aguardando geração de {len(batch_urls)} links ({wait_time:.1f}s)...")
                    time.sleep(wait_time)

                    # Busca textareas (deve haver 2: input e output)
                    textareas = page.query_selector_all('textarea.andes-form-control__field')

                    if len(textareas) < 2:
                        logger.warning(f"      ⚠️ Não encontrou output textarea (total: {len(textareas)})")
                        continue

                    # Extrai resultado (segunda textarea contém os links gerados, separados por quebra de linha)
                    result_text = page.evaluate('(el) => el.value', textareas[1])

                    if not result_text:
                        logger.warning(f"      ⚠️ Output vazio para {len(batch_urls)} URLs")
                        continue

                    # Separa os links gerados por quebra de linha
                    generated_links = result_text.strip().split('\n')

                    logger.info(f"      ✅ Recebido: {len(generated_links)} links do servidor")

                    # Mapeia URLs originais com links gerados
                    for original_url, generated_link in zip(batch_urls, generated_links):
                        generated_link = generated_link.strip()

                        if generated_link and generated_link != original_url:
                            results[original_url] = generated_link
                            logger.debug(f"         ✓ {original_url[:40]}... → {generated_link[:50]}...")
                        else:
                            logger.debug(f"         ⚠️ {original_url[:40]}... → sem link válido")

                except Exception as e:
                    logger.error(f"      ❌ Erro ao processar sub-lote {batch_num}: {e}")
                    continue

            logger.info(f"\n✅ Lote processado: {len(results)}/{len(product_urls)} links")
            return results

        except Exception as e:
            logger.error(f"❌ Erro ao processar URLs na página: {e}")
            return results


def main():
    """Função de teste"""
    try:
        gen = AffiliateLinkGenerator()

        # Teste com URLs de exemplo
        test_urls = [
            "https://www.mercadolivre.com.br/item/dummy-1",
            "https://www.mercadolivre.com.br/item/dummy-2",
        ]

        logger.info(f"🧪 Teste com {len(test_urls)} URLs")
        results = gen.generate_batch(test_urls)

        logger.info(f"\n📊 Resultados:")
        for original, affiliate in results.items():
            logger.info(f"  ✅ {original} → {affiliate[:60]}...")

    except Exception as e:
        logger.error(f"❌ Erro: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
