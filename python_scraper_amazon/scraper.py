"""
Amazon Affiliate Scraper - Script Principal
Scraper customizável que navega em URLs configuradas, captura ofertas,
gera links de afiliado via SiteStripe e salva no banco de dados.
"""
import os
import sys
import json
import yaml
import time
import logging
import re
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup

# Importar módulos locais
from db_manager import AmazonDatabaseManager
from capture_session import AmazonSessionCapture

load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            f'logs/scraper_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log',
            encoding='utf-8'
        )
    ]
)
logger = logging.getLogger(__name__)


class AmazonScraper:
    def __init__(self):
        """Inicializa o scraper com configurações"""
        self.config = self._load_config()
        self.db = AmazonDatabaseManager()
        self.session_capturer = AmazonSessionCapture()

        # Configurações de scraping
        self.selectors = self.config['scraping_settings']['selectors']
        self.delays = self.config['scraping_settings']['delays']
        self.timeouts = self.config['scraping_settings']['timeouts']

        # Estatísticas
        self.stats = {
            'urls_processed': 0,
            'products_found': 0,
            'products_saved': 0,
            'products_updated': 0,
            'products_ignored': 0,
            'errors': 0
        }

    def _load_config(self):
        """Carrega configurações do arquivo YAML"""
        try:
            config_path = Path('config.yml')
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"❌ Erro ao carregar config.yml: {e}")
            sys.exit(1)

    def _load_session(self, context):
        """Carrega sessão salva no contexto do navegador"""
        session_data = self.session_capturer.load_session()

        if not session_data:
            logger.error("❌ Nenhuma sessão encontrada. Execute capture_session.py primeiro!")
            return False

        try:
            # Adicionar cookies ao contexto
            context.add_cookies(session_data['cookies'])
            logger.info(f"✅ Sessão carregada com {len(session_data['cookies'])} cookies")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao carregar sessão: {e}")
            return False

    def extract_product_info(self, product_element, soup):
        """
        Extrai informações de um elemento de produto

        Args:
            product_element: Elemento BeautifulSoup do produto
            soup: BeautifulSoup da página completa

        Returns:
            dict: Dicionários com dados do produto ou None
        """
        try:
            # ASIN diretamente do atributo data-asin
            asin = product_element.get('data-asin')

            # Link do produto (primeiro link com href)
            link_elem = product_element.select_one(self.selectors['product_link'])
            if not link_elem or not link_elem.get('href'):
                # Tentar qualquer link
                link_elem = product_element.select_one('a[href*="/dp/"]')

            if not link_elem or not link_elem.get('href'):
                return None

            original_url = link_elem['href']
            if not original_url.startswith('http'):
                original_url = 'https://www.amazon.com.br' + original_url

            # Se não pegou ASIN do atributo, extrair da URL
            if not asin:
                asin = self._extract_asin(original_url)

            # Nome do produto - tentar múltiplos seletores
            product_name = None

            # Tentar pelo título padrão
            title_elem = product_element.select_one(self.selectors['product_title'])
            if title_elem:
                product_name = title_elem.get_text(strip=True)

            # Fallback: tentar pelo atributo alt da imagem
            if not product_name:
                img_elem = product_element.select_one('img[alt]')
                if img_elem and img_elem.get('alt'):
                    product_name = img_elem['alt']

            # Fallback: tentar truncate-cut
            if not product_name:
                truncate_elem = product_element.select_one('span.a-truncate-cut')
                if truncate_elem:
                    product_name = truncate_elem.get_text(strip=True)

            if not product_name:
                return None

            # Imagem
            image_elem = product_element.select_one('img')
            image_url = None
            if image_elem:
                image_url = image_elem.get('src') or image_elem.get('data-src')

            # Preços - buscar todos os spans a-offscreen com preços
            prices = []
            for price_span in product_element.select('span.a-offscreen'):
                price_text = price_span.get_text(strip=True)
                if 'R$' in price_text:
                    parsed = self._parse_price(price_text)
                    if parsed:
                        prices.append(parsed)

            # Ordenar preços - menor é sale_price, maior é list_price
            sale_price = None
            list_price = None
            if prices:
                prices = sorted(set(prices))
                sale_price = prices[0]
                if len(prices) > 1:
                    list_price = prices[-1]

            # Calcular desconto
            discount_percentage = None

            # Tentar pegar desconto do badge "30% off"
            discount_badge = product_element.select_one('div[data-component="dui-badge"] span.a-size-mini')
            if discount_badge:
                discount_text = discount_badge.get_text(strip=True)
                discount_match = re.search(r'(\d+)%', discount_text)
                if discount_match:
                    discount_percentage = int(discount_match.group(1))

            # Se não achou badge, calcular pelo preço
            if not discount_percentage and list_price and sale_price and list_price > sale_price:
                discount_percentage = int(((list_price - sale_price) / list_price) * 100)

            # Prime
            prime_elem = product_element.select_one(self.selectors['prime_badge'])
            prime_eligible = prime_elem is not None

            # Cupom
            has_coupon = False
            coupon_elem = product_element.select_one(self.selectors['coupon_badge'])
            if coupon_elem:
                has_coupon = True

            # Texto promocional (ex: "Oferta Black Friday")
            promotion_text = None
            promo_elem = product_element.select_one('div[data-component="dui-badge"] .style_badgeMessage__xR2lh span')
            if promo_elem:
                promotion_text = promo_elem.get_text(strip=True)

            return {
                'product_name': product_name,
                'original_url': original_url,
                'image_url': image_url,
                'asin': asin,
                'list_price': list_price,
                'sale_price': sale_price,
                'discount_percentage': discount_percentage,
                'has_coupon': has_coupon,
                'prime_eligible': prime_eligible,
                'rating': None,  # Não disponível nos cards Black Friday
                'review_count': None,
                'promotion_text': promotion_text
            }

        except Exception as e:
            logger.warning(f"⚠️ Erro ao extrair produto: {e}")
            return None

    def _extract_asin(self, url):
        """Extrai ASIN de uma URL da Amazon"""
        patterns = [
            r'/dp/([A-Z0-9]{10})',
            r'/gp/product/([A-Z0-9]{10})',
            r'ASIN=([A-Z0-9]{10})'
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def _parse_price(self, price_text):
        """
        Converte texto de preço para float
        Exemplo: "R$ 1.234,56" -> 1234.56
        """
        if not price_text:
            return None

        try:
            # Remover R$, espaços e converter vírgula para ponto
            price_clean = price_text.replace('R$', '').replace(' ', '').strip()
            price_clean = price_clean.replace('.', '').replace(',', '.')
            return float(price_clean)
        except:
            return None

    def scrape_listing_page(self, page, config):
        """
        Faz scraping de uma página de listagem de produtos

        IMPORTANTE: A Amazon usa paginação virtual com parâmetros na URL:
        - promotionsSearchStartIndex: índice de início (incrementa pelo page_size)
        - promotionsSearchPageSize: tamanho da página (90 para Black Friday)

        Para Best Sellers, usa estrutura diferente:
        - div.zg-grid-general-faceout para cards
        - Paginação via ?pg=N

        Args:
            page: Página Playwright
            config: Configuração da URL (do config.yml)

        Returns:
            list: Lista de produtos encontrados
        """
        logger.info(f"📄 Scraping: {config['name']} ({config['url']})")

        # Detectar tipo de página e usar método apropriado
        page_type = config.get('type', 'deal')
        if page_type == 'bestseller':
            return self._scrape_bestseller_page(page, config)

        max_products = config.get('max_offers', 50)
        collected_asins = set()  # Para evitar duplicatas
        products = []

        # Configuração de paginação da Amazon Black Friday:
        # - startIndex incrementa de 30 em 30
        # - pageSize = 60 até startIndex <= 330, depois muda para 90
        start_index = 0
        max_pages = (max_products // 25) + 5  # ~25 produtos por página
        empty_pages = 0  # Contador de páginas consecutivas sem produtos novos

        try:
            for page_num in range(max_pages):
                # PageSize muda de 60 para 90 após startIndex > 330
                page_size = 90 if start_index > 330 else 60

                # Construir URL com parâmetros de paginação
                base_url = config['url'].split('?')[0]  # Remove query params existentes
                if start_index == 0:
                    paginated_url = base_url
                else:
                    paginated_url = f"{base_url}?promotionsSearchStartIndex={start_index}&promotionsSearchPageSize={page_size}"

                logger.info(f"   📄 Página {page_num + 1}: startIndex={start_index}, pageSize={page_size}")

                # Navegar para URL paginada (usar domcontentloaded é mais rápido)
                try:
                    page.goto(paginated_url, wait_until='domcontentloaded', timeout=self.timeouts['page_load'])
                except PlaywrightTimeout:
                    logger.warning(f"   ⚠️ Timeout na página {page_num + 1}, tentando continuar...")
                    if page_num == 0:
                        raise  # Se falhar na primeira página, é erro real
                    break  # Em outras páginas, parar graciosamente

                # Aguardar carregamento extra para JavaScript
                time.sleep(3)

                # Aguardar grid de produtos aparecer
                try:
                    page.wait_for_selector('div[data-testid="virtuoso-item-list"]', timeout=10000)
                except:
                    if page_num == 0:
                        logger.warning("⚠️ Grid virtualizado não encontrado na primeira página")
                    else:
                        logger.info("📊 Não há mais páginas de produtos")
                    break

                # Debug: contar quantos cards existem na página
                all_cards = page.query_selector_all('div[data-testid="product-card"]')
                logger.debug(f"   🔍 Cards encontrados na página: {len(all_cards)}")

                # Fazer scroll na página para carregar todos os produtos visíveis
                products_before = len(products)
                products_in_page = self._collect_products_from_page(page, collected_asins, config)

                for product in products_in_page:
                    if len(products) >= max_products:
                        break
                    products.append(product)

                new_count = len(products) - products_before
                logger.info(f"   📦 Coletados +{new_count} produtos (cards na página: {len(all_cards)}) → Total: {len(products)}")

                # Verificar se já temos produtos suficientes
                if len(products) >= max_products:
                    logger.info(f"✅ Atingido limite de {max_products} produtos")
                    break

                # Contador de páginas consecutivas sem produtos novos
                if new_count == 0:
                    empty_pages += 1
                    logger.info(f"   ⚠️ Página sem produtos novos ({empty_pages}/3)")
                    if empty_pages >= 3:
                        logger.info("📊 3 páginas consecutivas sem produtos novos - parando")
                        break
                else:
                    empty_pages = 0  # Reset se encontrou produtos

                # Próxima página
                start_index += 30

            if not products:
                # Salvar HTML para debug
                html = page.content()
                debug_path = Path('debug_page.html')
                with open(debug_path, 'w', encoding='utf-8') as f:
                    f.write(html)
                logger.warning(f"⚠️ Nenhum produto encontrado em {config['url']}")
                logger.info(f"   HTML salvo em {debug_path} para debug")
                return []

            logger.info(f"🔍 Total coletado: {len(products)} produtos únicos")

            # Log dos produtos coletados
            for idx, product_data in enumerate(products[:max_products], 1):
                logger.info(f"  ✅ [{idx}/{len(products)}] {product_data['product_name'][:60]}...")

            logger.info(f"📊 Total extraído: {len(products)} produtos")
            return products[:max_products]  # Limitar ao máximo configurado

        except PlaywrightTimeout:
            logger.error(f"❌ Timeout ao carregar {config['url']}")
            return []
        except Exception as e:
            logger.error(f"❌ Erro ao scraping {config['url']}: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _scrape_bestseller_page(self, page, config):
        """
        Faz scraping de páginas Best Sellers da Amazon

        Best Sellers usam estrutura diferente:
        - Cards: div.zg-grid-general-faceout
        - ASIN: div[data-asin]
        - Título: div._cDEzb_p13n-sc-css-line-clamp-1_1Fn1y
        - Preço: span._cDEzb_p13n-sc-price_3mJ9Z
        - Paginação: ?pg=N (1-2 normalmente, 50 produtos cada)

        Args:
            page: Página Playwright
            config: Configuração da URL

        Returns:
            list: Lista de produtos encontrados
        """
        max_products = config.get('max_offers', 50)
        collected_asins = set()
        products = []

        # Best Sellers tem normalmente 2 páginas de 50 produtos cada
        max_pages = (max_products // 50) + 1

        try:
            for page_num in range(1, max_pages + 1):
                # Construir URL paginada
                base_url = config['url'].split('?')[0]
                paginated_url = f"{base_url}?pg={page_num}" if page_num > 1 else base_url

                logger.info(f"   📄 Best Sellers página {page_num}: {paginated_url}")

                # Navegar
                try:
                    page.goto(paginated_url, wait_until='domcontentloaded', timeout=self.timeouts['page_load'])
                except PlaywrightTimeout:
                    logger.warning(f"   ⚠️ Timeout na página {page_num}")
                    if page_num == 1:
                        raise
                    break

                # Aguardar carregamento
                time.sleep(2)

                # Verificar se há produtos (seletor de Best Sellers)
                try:
                    page.wait_for_selector('div.zg-grid-general-faceout, div[id^="gridItemRoot"]', timeout=10000)
                except:
                    if page_num == 1:
                        logger.warning("⚠️ Grid de Best Sellers não encontrado")
                        # Salvar HTML para debug
                        html = page.content()
                        debug_path = Path('debug_page.html')
                        with open(debug_path, 'w', encoding='utf-8') as f:
                            f.write(html)
                        logger.info(f"   HTML salvo em {debug_path} para debug")
                    break

                # Fazer scroll para carregar todos os produtos
                for _ in range(5):
                    page.evaluate('window.scrollBy(0, window.innerHeight)')
                    time.sleep(0.3)

                # Coletar produtos desta página
                products_before = len(products)
                page_products = self._collect_bestseller_products(page, collected_asins, config)

                for product in page_products:
                    if len(products) >= max_products:
                        break
                    products.append(product)

                new_count = len(products) - products_before
                logger.info(f"   📦 Coletados +{new_count} produtos → Total: {len(products)}")

                if len(products) >= max_products:
                    logger.info(f"✅ Atingido limite de {max_products} produtos")
                    break

                if new_count == 0:
                    logger.info("📊 Não há mais produtos")
                    break

            if products:
                logger.info(f"🔍 Total Best Sellers: {len(products)} produtos")
                for idx, p in enumerate(products[:10], 1):
                    logger.info(f"  ✅ [{idx}] {p['product_name'][:60]}...")
                if len(products) > 10:
                    logger.info(f"  ... e mais {len(products) - 10} produtos")

            return products[:max_products]

        except Exception as e:
            logger.error(f"❌ Erro no Best Sellers {config['url']}: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _collect_bestseller_products(self, page, collected_asins, config):
        """
        Coleta produtos de uma página Best Sellers

        Args:
            page: Página Playwright
            collected_asins: Set de ASINs já coletados
            config: Configuração da URL

        Returns:
            list: Produtos coletados
        """
        products = []

        # Encontrar todos os cards de produto
        # Os cards têm data-asin e estão dentro de div.zg-grid-general-faceout
        cards = page.query_selector_all('div[data-asin]')

        logger.debug(f"   🔍 Cards com data-asin encontrados: {len(cards)}")

        for card in cards:
            try:
                asin = card.get_attribute('data-asin')
                if not asin or len(asin) != 10:
                    continue

                if asin in collected_asins:
                    continue

                product_data = self._extract_bestseller_product(card)

                if product_data and product_data.get('asin'):
                    collected_asins.add(product_data['asin'])
                    product_data['source_url'] = config['url']
                    product_data['scrape_type'] = 'bestseller'
                    product_data['category'] = config.get('category')
                    products.append(product_data)

            except Exception as e:
                logger.debug(f"Erro ao extrair card bestseller: {e}")

        return products

    def _extract_bestseller_product(self, card):
        """
        Extrai informações de um card de Best Sellers

        Estrutura Best Sellers:
        - ASIN: div[data-asin]
        - Título: div._cDEzb_p13n-sc-css-line-clamp-1_1Fn1y ou line-clamp-3
        - Preço: span._cDEzb_p13n-sc-price_3mJ9Z
        - Imagem: img.p13n-product-image
        - Rating: i.a-icon-star-small (aria-label contém "X de 5 estrelas")
        - Reviews: span após o rating
        - Ranking: span.zg-bdg-text (ex: "#1", "#15")

        Args:
            card: ElementHandle do Playwright

        Returns:
            dict: Dados do produto ou None
        """
        try:
            asin = card.get_attribute('data-asin')

            # Link do produto
            link_elem = card.query_selector('a[href*="/dp/"]')
            if not link_elem:
                return None

            original_url = link_elem.get_attribute('href')
            if not original_url:
                return None
            if not original_url.startswith('http'):
                original_url = 'https://www.amazon.com.br' + original_url

            # Nome do produto - tentar múltiplos seletores
            product_name = None

            # Seletores de título Best Sellers (classes dinâmicas com _cDEzb_)
            title_selectors = [
                'div[class*="p13n-sc-css-line-clamp"]',
                'span[class*="p13n-sc-css-line-clamp"]',
            ]

            for selector in title_selectors:
                title_elem = card.query_selector(selector)
                if title_elem:
                    text = title_elem.inner_text()
                    if text and len(text) > 5:
                        product_name = text
                        break

            # Fallback: alt da imagem
            if not product_name:
                img_elem = card.query_selector('img[alt]')
                if img_elem:
                    product_name = img_elem.get_attribute('alt')

            if not product_name:
                return None

            # Imagem
            image_url = None
            img_elem = card.query_selector('img.p13n-product-image, img.p13n-sc-dynamic-image')
            if img_elem:
                image_url = img_elem.get_attribute('src')

            # Preço - seletor específico de Best Sellers
            sale_price = None
            price_elem = card.query_selector('span[class*="p13n-sc-price"]')
            if price_elem:
                price_text = price_elem.inner_text()
                sale_price = self._parse_price(price_text)

            # Rating
            rating = None
            rating_elem = card.query_selector('i[class*="a-icon-star"] span.a-icon-alt')
            if rating_elem:
                rating_text = rating_elem.inner_text()
                # "4,8 de 5 estrelas"
                match = re.search(r'([\d,]+)\s+de\s+5', rating_text)
                if match:
                    rating = float(match.group(1).replace(',', '.'))

            # Review count
            review_count = None
            review_elem = card.query_selector('a[href*="/product-reviews/"] span.a-size-small')
            if review_elem:
                review_text = review_elem.inner_text()
                # Remover pontos e vírgulas, pegar só números
                review_text = re.sub(r'[^\d]', '', review_text)
                if review_text:
                    review_count = int(review_text)

            # Ranking (posição no best sellers)
            ranking = None
            rank_elem = card.query_selector('span.zg-bdg-text')
            if rank_elem:
                rank_text = rank_elem.inner_text()
                # "#15" -> 15
                rank_match = re.search(r'#?(\d+)', rank_text)
                if rank_match:
                    ranking = int(rank_match.group(1))

            return {
                'product_name': product_name,
                'original_url': original_url,
                'image_url': image_url,
                'asin': asin,
                'list_price': None,  # Best Sellers não mostra preço original
                'sale_price': sale_price,
                'discount_percentage': None,
                'has_coupon': False,
                'prime_eligible': False,
                'rating': rating,
                'review_count': review_count,
                'promotion_text': f"Best Seller #{ranking}" if ranking else "Best Seller"
            }

        except Exception as e:
            logger.debug(f"Erro extraindo bestseller: {e}")
            return None

    def _collect_products_from_page(self, page, collected_asins, config):
        """
        Coleta todos os produtos de uma página fazendo scroll

        Args:
            page: Página Playwright
            collected_asins: Set de ASINs já coletados
            config: Configuração da URL

        Returns:
            list: Produtos coletados nesta página
        """
        products = []
        no_new_count = 0
        duplicates_count = 0

        # Fazer scroll progressivo na página para carregar todos os produtos
        for scroll_num in range(15):  # Máximo de scrolls por página
            current_cards = page.query_selector_all('div[data-testid="product-card"]')

            new_in_scroll = 0
            for card in current_cards:
                try:
                    asin = card.get_attribute('data-asin')
                    if not asin:
                        continue
                    if asin in collected_asins:
                        duplicates_count += 1
                        continue

                    product_data = self._extract_product_from_element(card)

                    if product_data and product_data.get('asin'):
                        collected_asins.add(product_data['asin'])
                        product_data['source_url'] = config['url']
                        product_data['scrape_type'] = config.get('type', 'product')
                        product_data['category'] = config.get('category')  # Categoria do config
                        products.append(product_data)
                        new_in_scroll += 1

                except Exception as e:
                    logger.debug(f"Erro ao extrair card: {e}")

            if new_in_scroll > 0:
                no_new_count = 0
            else:
                no_new_count += 1

            # Se não encontrou produtos novos em 3 scrolls, parar
            if no_new_count >= 3:
                logger.debug(f"   🔄 Scroll {scroll_num+1}: {len(current_cards)} cards, {duplicates_count} duplicados")
                break

            # Scroll para baixo
            page.evaluate('window.scrollBy(0, window.innerHeight * 1.2)')
            time.sleep(0.5)

        return products

    def _extract_product_from_element(self, card):
        """
        Extrai informações de um card de produto usando Playwright Element

        Args:
            card: ElementHandle do Playwright

        Returns:
            dict: Dados do produto ou None
        """
        try:
            # ASIN do atributo data-asin
            asin = card.get_attribute('data-asin')

            # Link do produto
            link_elem = card.query_selector('a[href*="/dp/"]')
            if not link_elem:
                link_elem = card.query_selector('a[data-testid="product-card-link"]')

            if not link_elem:
                return None

            original_url = link_elem.get_attribute('href')
            if not original_url:
                return None
            if not original_url.startswith('http'):
                original_url = 'https://www.amazon.com.br' + original_url

            # Se não pegou ASIN do atributo, extrair da URL
            if not asin:
                asin = self._extract_asin(original_url)

            # Nome do produto - tentar vários seletores
            product_name = None

            # Tentar pelo alt da imagem (mais confiável)
            img_elem = card.query_selector('img[alt]')
            if img_elem:
                product_name = img_elem.get_attribute('alt')

            # Fallback: título
            if not product_name:
                title_elem = card.query_selector('span.a-truncate-full')
                if title_elem:
                    product_name = title_elem.inner_text()

            if not product_name:
                title_elem = card.query_selector('p[id^="title-"]')
                if title_elem:
                    product_name = title_elem.inner_text()

            if not product_name:
                return None

            # Imagem
            image_url = None
            if img_elem:
                image_url = img_elem.get_attribute('src')

            # Preços - pegar todos os offscreen
            prices = []
            price_spans = card.query_selector_all('span.a-offscreen')
            for span in price_spans:
                price_text = span.inner_text()
                if 'R$' in price_text:
                    parsed = self._parse_price(price_text)
                    if parsed:
                        prices.append(parsed)

            # Ordenar preços
            sale_price = None
            list_price = None
            if prices:
                prices = sorted(set(prices))
                sale_price = prices[0]
                if len(prices) > 1:
                    list_price = prices[-1]

            # Desconto do badge
            discount_percentage = None
            discount_badge = card.query_selector('div[data-component="dui-badge"] span.a-size-mini')
            if discount_badge:
                discount_text = discount_badge.inner_text()
                discount_match = re.search(r'(\d+)%', discount_text)
                if discount_match:
                    discount_percentage = int(discount_match.group(1))

            # Calcular desconto se não veio do badge
            if not discount_percentage and list_price and sale_price and list_price > sale_price:
                discount_percentage = int(((list_price - sale_price) / list_price) * 100)

            # Texto promocional
            promotion_text = None
            promo_elem = card.query_selector('.style_badgeMessage__xR2lh span')
            if promo_elem:
                promotion_text = promo_elem.inner_text()

            return {
                'product_name': product_name,
                'original_url': original_url,
                'image_url': image_url,
                'asin': asin,
                'list_price': list_price,
                'sale_price': sale_price,
                'discount_percentage': discount_percentage,
                'has_coupon': False,
                'prime_eligible': False,
                'rating': None,
                'review_count': None,
                'promotion_text': promotion_text
            }

        except Exception as e:
            logger.debug(f"Erro extraindo produto: {e}")
            return None

    def _scroll_page(self, page):
        """Scroll suave na página para carregar lazy loading"""
        max_scrolls = self.config['scraping_settings']['navigation']['max_scroll_attempts']
        scroll_delay = self.config['scraping_settings']['navigation']['scroll_delay']

        for i in range(max_scrolls):
            page.evaluate('window.scrollBy(0, window.innerHeight)')
            time.sleep(scroll_delay / 1000)

    def generate_affiliate_link(self, page, product_data):
        """
        Navega para o produto, captura dados detalhados e gera link de afiliado via SiteStripe.

        CAPTURA DA PÁGINA DO PRODUTO:
        - Preço promocional (sale_price): span.a-price.priceToPay
        - Preço original (list_price): span.a-price.a-text-price[data-a-strike="true"]
        - Parcelamento (installment_info): #best-offer-string-cc
        - Frete (shipping_info): span[data-csa-c-delivery-price]
        - Promoções (promotion_text): .promoPriceBlockMessage (múltiplas, separadas por |||)

        Args:
            page: Página Playwright
            product_data: Dados do produto (será atualizado com dados da página)

        Returns:
            str: Link de afiliado ou None se falhar
        """
        logger.info(f"🔗 Gerando link de afiliado para: {product_data['product_name'][:50]}...")

        try:
            # Navegar para página do produto
            page.goto(product_data['original_url'], wait_until='domcontentloaded', timeout=self.timeouts['page_load'])

            # Aguardar página carregar
            time.sleep(self.delays['sitestripe_load'])

            # ========================================
            # CAPTURAR DADOS DETALHADOS DA PÁGINA
            # ========================================

            # 1. PREÇO PROMOCIONAL (sale_price) - priceToPay
            try:
                # Método 1: Pegar via whole + fraction (mais confiável)
                whole_elem = page.query_selector('span.priceToPay span.a-price-whole')
                fraction_elem = page.query_selector('span.priceToPay span.a-price-fraction')

                if whole_elem and fraction_elem:
                    whole_text = whole_elem.inner_text().replace(',', '').replace('.', '').replace('\n', '').strip()
                    fraction_text = fraction_elem.inner_text().replace('\n', '').strip()
                    logger.info(f"  💰 Preço whole={whole_text}, fraction={fraction_text}")
                    if whole_text and fraction_text:
                        new_sale_price = float(f"{whole_text}.{fraction_text}")
                        product_data['sale_price'] = new_sale_price
                        logger.info(f"  💰 Preço promocional capturado: R${new_sale_price}")
                else:
                    # Método 2: Fallback para offscreen
                    logger.debug(f"  ⚠️ Seletores whole/fraction não encontrados")
                    price_elem = page.query_selector('#corePrice_feature_div span.a-offscreen, #corePriceDisplay_desktop_feature_div span.a-offscreen')
                    if price_elem:
                        price_text = price_elem.inner_text()
                        new_sale_price = self._parse_price(price_text)
                        if new_sale_price:
                            product_data['sale_price'] = new_sale_price
                            logger.info(f"  💰 Preço promocional (fallback): R${new_sale_price}")
            except Exception as e:
                logger.warning(f"  ⚠️ Erro ao capturar preço promocional: {e}")

            # 2. PREÇO ORIGINAL (list_price) - preço riscado "De:"
            try:
                # Seletor baseado no HTML: span.a-price.a-text-price com data-a-strike="true"
                list_price_elem = page.query_selector('span.a-price.a-text-price[data-a-strike="true"] span.a-offscreen')
                if not list_price_elem:
                    # Fallback: basisPrice
                    list_price_elem = page.query_selector('.basisPrice span.a-offscreen')

                if list_price_elem:
                    list_price_text = list_price_elem.inner_text()
                    new_list_price = self._parse_price(list_price_text)
                    if new_list_price:
                        product_data['list_price'] = new_list_price
                        logger.info(f"  💵 Preço original capturado: R${new_list_price}")
            except Exception as e:
                logger.warning(f"  ⚠️ Erro ao capturar preço original: {e}")            # 3. PARCELAMENTO (installment_info)
            try:
                installment_elem = page.query_selector('#best-offer-string-cc')
                if installment_elem:
                    installment_text = installment_elem.inner_text().strip()
                    if installment_text:
                        product_data['installment_info'] = installment_text
                        logger.debug(f"  💳 Parcelamento: {installment_text[:50]}...")
            except Exception as e:
                logger.debug(f"  ⚠️ Erro ao capturar parcelamento: {e}")

            # 4. FRETE (shipping_info)
            try:
                # Tentar pegar do atributo data-csa-c-delivery-price
                shipping_elem = page.query_selector('span[data-csa-c-delivery-price]')
                if shipping_elem:
                    delivery_price = shipping_elem.get_attribute('data-csa-c-delivery-price')
                    delivery_time = shipping_elem.get_attribute('data-csa-c-delivery-time') or ''

                    if delivery_price:
                        shipping_info = f"{delivery_price}"
                        if delivery_time:
                            shipping_info += f" - {delivery_time}"
                        product_data['shipping_info'] = shipping_info
                        logger.debug(f"  🚚 Frete: {shipping_info}")
            except Exception as e:
                logger.debug(f"  ⚠️ Erro ao capturar frete: {e}")

            # 5. PROMOÇÕES/CUPONS (promotion_text) - múltiplas, separadas por |||
            try:
                promo_container = page.query_selector('span.promoPriceBlockMessage')
                if promo_container:
                    promotions = []

                    # Buscar todas as divs de promoção dentro do container
                    promo_divs = promo_container.query_selector_all('div[style*="padding"]')

                    for promo_div in promo_divs:
                        promo_text = ""

                        # Tentar pegar o badge (ex: "R$300" ou "Oferta")
                        badge = promo_div.query_selector('label[id^="greenBadge"]')
                        if badge:
                            badge_text = badge.inner_text().strip()
                            promo_text = badge_text + " "

                        # Pegar a mensagem da promoção
                        msg_span = promo_div.query_selector('span[id^="promoMessage"]')
                        if msg_span:
                            # Pegar apenas o texto, não os links
                            msg_text = msg_span.inner_text().strip()
                            # Limpar texto (remover "Ver itens participantes", "Termos", etc.)
                            msg_text = re.sub(r'\s*(Ver itens participantes|Termos)\s*', '', msg_text)
                            msg_text = msg_text.strip()
                            promo_text += msg_text

                        if promo_text.strip():
                            promotions.append(promo_text.strip())

                    if promotions:
                        # Juntar com ||| como separador
                        product_data['promotion_text'] = '|||'.join(promotions)
                        product_data['has_coupon'] = True
                        logger.debug(f"  🎟️ Promoções: {len(promotions)} encontradas")
                        for p in promotions:
                            logger.debug(f"      - {p[:60]}...")
            except Exception as e:
                logger.debug(f"  ⚠️ Erro ao capturar promoções: {e}")

            # Recalcular desconto com preços atualizados
            if product_data.get('list_price') and product_data.get('sale_price'):
                list_p = product_data['list_price']
                sale_p = product_data['sale_price']
                if list_p > sale_p:
                    product_data['discount_percentage'] = int(((list_p - sale_p) / list_p) * 100)

            # ========================================
            # GERAR LINK DE AFILIADO VIA SITESTRIPE
            # ========================================

            sitestripe_link = None

            try:
                # Aguardar botão "Obter link" do SiteStripe aparecer
                get_link_button = page.wait_for_selector('#amzn-ss-get-link-button', timeout=self.timeouts['sitestripe_wait'])

                if get_link_button:
                    logger.debug("  📍 Botão SiteStripe encontrado, clicando...")

                    # Clicar no botão "Obter link"
                    get_link_button.click()

                    # Aguardar o modal/textarea aparecer
                    time.sleep(1.5)

                    # Tentar pegar o link do textarea
                    link_textarea = page.wait_for_selector('#amzn-ss-text-shortlink-textarea', timeout=5000)

                    if link_textarea:
                        sitestripe_link = link_textarea.input_value()

                        # Verificar se é um link válido
                        if sitestripe_link and 'amzn.to' in sitestripe_link:
                            logger.info(f"  ✅ Link SiteStripe gerado: {sitestripe_link}")
                            return sitestripe_link
                        else:
                            logger.warning(f"  ⚠️ Link inválido no textarea: {sitestripe_link}")

            except PlaywrightTimeout:
                logger.debug("  ⚠️ SiteStripe não encontrado ou timeout")

            except Exception as e:
                logger.debug(f"  ⚠️ Erro ao usar SiteStripe: {e}")

            # Fallback: gerar link manualmente com tag de afiliado
            asin = product_data.get('asin')
            if asin:
                associate_tag = os.getenv('AMAZON_ASSOCIATE_TAG', '')
                if associate_tag:
                    sitestripe_link = f"https://www.amazon.com.br/dp/{asin}/?tag={associate_tag}"
                    logger.info(f"  ✅ Link manual gerado com tag: {associate_tag}")
                    return sitestripe_link

            logger.warning(f"  ❌ Não foi possível gerar link de afiliado")
            return None

        except Exception as e:
            logger.error(f"❌ Erro ao gerar link de afiliado: {e}")
            return None

    def process_product(self, page, product_data):
        """
        Processa um produto: gera link de afiliado e salva no banco

        Args:
            page: Página Playwright
            product_data: Dados do produto

        Returns:
            str: Resultado ('inserted', 'updated', 'ignored', 'error')
        """
        # Gerar link de afiliado
        affiliate_link = self.generate_affiliate_link(page, product_data)

        if not affiliate_link:
            logger.warning(f"  ⏭️ Produto ignorado (sem link de afiliado)")
            return 'error'

        # Adicionar link de afiliado aos dados
        product_data['affiliate_url'] = affiliate_link

        # Salvar no banco
        result = self.db.insert_offer(product_data)

        if result == 'inserted':
            self.stats['products_saved'] += 1
        elif result == 'updated':
            self.stats['products_updated'] += 1
        elif result == 'ignored':
            self.stats['products_ignored'] += 1
        else:
            self.stats['errors'] += 1

        # Delay entre produtos
        time.sleep(self.delays['between_products'])

        return result

    def run(self):
        """Executa o scraper completo"""
        logger.info("=" * 70)
        logger.info("AMAZON AFFILIATE SCRAPER")
        logger.info("=" * 70)
        logger.info(f"Iniciado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        logger.info("")

        # Validar sessão
        if not self.session_capturer.validate_session():
            logger.error("❌ Sessão inválida. Execute capture_session.py primeiro!")
            return

        # Testar conexão com banco
        if not self.db.test_connection():
            logger.error("❌ Falha na conexão com banco de dados!")
            return

        # Pegar URLs habilitadas
        enabled_configs = [c for c in self.config['scraping_configs'] if c.get('enabled', True)]

        if not enabled_configs:
            logger.warning("⚠️ Nenhuma URL habilitada no config.yml")
            return

        logger.info(f"📋 {len(enabled_configs)} URL(s) para processar")
        logger.info("")

        # Iniciar navegador (headless por padrão para não atrapalhar o usuário)
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=os.getenv('HEADLESS', 'True').lower() == 'true',
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu'
                ]
            )

            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                locale='pt-BR',
                timezone_id='America/Sao_Paulo'
            )

            # Carregar sessão
            if not self._load_session(context):
                browser.close()
                return

            page = context.new_page()

            try:
                # Processar cada URL configurada
                for url_config in enabled_configs:
                    self.stats['urls_processed'] += 1

                    # Scraping da listagem
                    products = self.scrape_listing_page(page, url_config)
                    self.stats['products_found'] += len(products)

                    if not products:
                        continue

                    # Processar cada produto
                    logger.info("")
                    logger.info(f"🔄 Processando {len(products)} produtos...")
                    logger.info("")

                    for idx, product_data in enumerate(products, 1):
                        logger.info(f"[{idx}/{len(products)}] Processando: {product_data['product_name'][:50]}...")
                        self.process_product(page, product_data)

                    logger.info("")
                    logger.info(f"✅ URL concluída: {url_config['name']}")
                    logger.info("")

            finally:
                browser.close()

        # Relatório final
        self._print_report()

    def _print_report(self):
        """Imprime relatório final"""
        logger.info("=" * 70)
        logger.info("RELATÓRIO FINAL")
        logger.info("=" * 70)
        logger.info(f"URLs processadas:      {self.stats['urls_processed']}")
        logger.info(f"Produtos encontrados:  {self.stats['products_found']}")
        logger.info(f"Produtos INSERIDOS:    {self.stats['products_saved']}")
        logger.info(f"Produtos ATUALIZADOS:  {self.stats['products_updated']}")
        logger.info(f"Produtos IGNORADOS:    {self.stats['products_ignored']}")
        logger.info(f"Erros:                 {self.stats['errors']}")
        logger.info("=" * 70)
        logger.info(f"Concluído em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        logger.info("=" * 70)


def main():
    """Função principal"""
    scraper = AmazonScraper()
    scraper.run()


if __name__ == '__main__':
    main()
