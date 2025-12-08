"""
Scraper de ofertas do Mercado Livre usando Playwright
Suporta múltiplas URLs de scraping
"""
import os
import logging
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# Obter logger (herdará configuração de main.py)
logger = logging.getLogger(__name__)

class MeliScraper:
    def __init__(self):
        self.max_pages = int(os.getenv('MAX_PAGES', 1))

        # Carregar URLs de scraping do .env
        scraping_urls_str = os.getenv('SCRAPING_URLS', 'https://www.mercadolivre.com.br/ofertas?page=1')
        self.scraping_urls = [url.strip() for url in scraping_urls_str.split(',')]

        print(f"\n📋 URLs configuradas para scraping:")
        for i, url in enumerate(self.scraping_urls, 1):
            print(f"   {i}. {url[:80]}...")

    def scrape_offers(self, url, page_num=1):
        """
        Faz scraping de uma página de ofertas

        Args:
            url (str): URL base para scraping
            page_num (int): Número da página (1-indexed)

        Returns:
            list: Lista de dicionários com dados dos produtos
        """
        # Verificar se a URL já tem ?page= ou &page=
        if '&page=' in url or '?page=' in url:
            # Substituir page existente
            import re
            url = re.sub(r'[?&]page=\d+', f'&page={page_num}', url)
            # Se ainda não tiver &, adicionar depois de ?
            if '?' not in url:
                url += f'?page={page_num}'
        else:
            # Adicionar page parameter
            separator = '&' if '?' in url else '?'
            url += f'{separator}page={page_num}'

        print(f"\n 📄 Baixando página {page_num}...")
        print(f" URL: {url[:90]}..." if len(url) > 90 else f" URL: {url}")

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox'
                ]
            )

            # Cria contexto com headers realistas
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='pt-BR',
                timezone_id='America/Sao_Paulo'
            )

            page = context.new_page()

            try:
                # Navega para a página
                page.goto(url, wait_until='domcontentloaded', timeout=30000)

                # Aguarda um pouco para conteúdo dinâmico carregar
                page.wait_for_timeout(5000)

                # Faz scroll para carregar lazy loading
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2000)

                # Tenta aguardar produtos, mas não falha se não encontrar
                try:
                    page.wait_for_selector('.poly-card--grid-card', timeout=10000)
                    print("OK: Produtos encontrados!")
                except:
                    print("AVISO: Seletor de produtos não encontrado, tentando extrair mesmo assim...")

                html_content = page.content()

                # Salva HTML para debug com caminho absoluto
                debug_path = os.path.join(os.path.dirname(__file__), f"debug_page_{page_num}.html")
                with open(debug_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                print(f" HTML salvo em: {debug_path}")

                # Verificar se página tem produtos ANTES de processar
                if not self._has_products(html_content):
                    print(f"⚠️  PÁGINA {page_num} SEM PRODUTOS - Pulando...")
                    browser.close()
                    return []

                browser.close()

                # Processa HTML com BeautifulSoup
                return self._parse_html(html_content)

            except Exception as e:
                print(f"ERRO: Erro ao baixar página {page_num}: {e}")
                browser.close()
                return []

    def _has_products(self, html_content):
        """
        Verifica se a página tem PRODUTOS (não apenas estrutura do site)

        Procura especificamente por elementos que indicam presença de produtos,
        ignorando menus, navbars, footer e carousels de navegação.

        Args:
            html_content (str): HTML da página

        Returns:
            bool: True se houver produtos, False caso não haja
        """
        soup = BeautifulSoup(html_content, 'html.parser')

        # 1. Verificar pelo seletor antigo (poly-card--grid-card)
        poly_cards = soup.select('div.poly-card--grid-card')
        if poly_cards and len(poly_cards) > 0:
            return True

        # 2. Verificar pelo container de itens com produtos
        items_smart_groups = soup.find('div', class_='items-with-smart-groups')
        if items_smart_groups:
            # Verificar se tem links de produtos (href com /p/)
            product_links = items_smart_groups.find_all('a', href=lambda x: x and '/mlb' in x.lower() and '/p/' in x)
            if product_links and len(product_links) > 0:
                return True

            # Verificar se tem divs internas com conteúdo significativo
            internal_divs = items_smart_groups.find_all('div', recursive=False)
            for div in internal_divs:
                text = div.get_text(strip=True)
                links = div.find_all('a')
                # Se tem links de produto
                product_links_in_div = [l for l in links if '/p/' in l.get('href', '')]
                if product_links_in_div and len(product_links_in_div) > 0:
                    return True

        # 3. Verificar por links de produtos em geral dentro de main
        # (ignorar navbar, carousel, footer)
        main = soup.find('main')
        if main:
            # Procurar especificamente por links que pareçam ser de produtos
            all_links = main.find_all('a')
            product_links_count = 0

            for link in all_links:
                href = link.get('href', '')
                # Links de produtos no Mercado Livre
                if '/mlb' in href.lower() and '/p/' in href:
                    product_links_count += 1

            # Se encontrou pelo menos 5 links de produtos
            if product_links_count >= 5:
                return True
        # 4. Verificar divs com classes que pareçam ser cards/itens
        # MAS excluir os containers de layout vazios (items, items-list, items-with-smart-groups, etc)
        potential = soup.find_all('div', class_=lambda x: x and any(
            p in str(x).lower() for p in ['card', 'item', 'product', 'offer']
        ))

        # Filtrar exclusões
        exclusions = ['items', 'items-list', 'items-with-smart-groups', 'nav', 'menu', 'carousel', 'header', 'footer']

        real_products = []
        for p in potential:
            cls_str = str(p.get('class', []))
            # Verificar se tem alguma palavra de exclusão
            has_exclusion = any(exc in cls_str.lower() for exc in exclusions)

            if not has_exclusion:
                real_products.append(p)

        if real_products and len(real_products) > 0:
            return True

        # Se nenhum indicador de produto foi encontrado
        return False

    def _parse_html(self, html_content):
        """
        Extrai produtos do HTML usando BeautifulSoup

        Args:
            html_content (str): HTML da página

        Returns:
            list: Lista de produtos extraídos
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        # Busca elementos que CONTENHAM a classe poly-card--grid-card (não precisa ser exata)
        cards = soup.select('div.poly-card--grid-card')

        print(f" Encontrados {len(cards)} cards de produtos no HTML")

        products = []

        for card in cards:
            try:
                # URL e Nome
                link_tag = card.find('a', class_='poly-component__title')
                if not link_tag:
                    continue

                original_url = link_tag.get('href', '').split('#')[0]  # Remove tracking
                product_name = link_tag.text.strip()

                # Imagem
                image_tag = card.find('img', class_='poly-component__picture')
                image_url = None
                if image_tag:
                    image_url = image_tag.get('data-src') or image_tag.get('src')

                # Preço Original
                list_price_tag = card.find('s', class_='andes-money-amount--previous')
                list_price = None
                if list_price_tag:
                    list_price = self._clean_price(list_price_tag.text)

                # Preço Promocional
                sale_price = None
                sale_container = card.find('span', class_='andes-money-amount--cents-superscript')
                if sale_container:
                    fraction = sale_container.find('span', class_='andes-money-amount__fraction')
                    cents = sale_container.find('span', class_='andes-money-amount__cents')

                    if fraction and cents:
                        sale_price = self._clean_price(f"{fraction.text},{cents.text}")
                    elif fraction:
                        sale_price = self._clean_price(fraction.text)

                # Parcelamento
                installments_tag = card.find('span', class_='poly-price__installments')
                installments = installments_tag.text.strip() if installments_tag else None

                # Frete
                shipping_tag = card.find('div', class_='poly-component__shipping')
                shipping = shipping_tag.text.strip() if shipping_tag else None

                # FULL
                is_full = card.find('svg', class_='poly-shipping__promise-icon--full') is not None

                # Só adiciona se tiver dados essenciais
                if product_name and sale_price and original_url:
                    products.append({
                        'product_name': product_name,
                        'original_url': original_url,
                        'image_url': image_url,
                        'list_price': list_price,
                        'sale_price': sale_price,
                        'installments_info': installments,
                        'shipping_info': shipping,
                        'is_full': is_full
                    })

            except Exception as e:
                print(f"AVISO: Erro ao processar card: {e}")
                continue

        print(f"OK: Extraídos {len(products)} produtos")
        return products

    def _clean_price(self, price_str):
        """
        Converte string de preço para float

        Args:
            price_str (str): Ex: "R$ 1.299,99" ou "1.299,99"

        Returns:
            float: Preço numérico
        """
        try:
            cleaned = price_str.replace('R$', '').replace('.', '').replace(',', '.').strip()
            return float(cleaned)
        except:
            return None

    def scrape_all_pages(self):
        """
        Faz scraping de todas as URLs e páginas configuradas

        Returns:
            list: Lista completa de produtos de todas as URLs e páginas
        """
        all_products = []
        pages_with_products = 0
        pages_without_products = 0

        print(f"\n🔍 Iniciando scraping de {len(self.scraping_urls)} URL(s)...")
        print(f"   {self.max_pages} página(s) por URL")
        print(f"   Total esperado: ~{len(self.scraping_urls) * self.max_pages} requisições\n")

        # Loop por cada URL configurada
        for url_idx, base_url in enumerate(self.scraping_urls, 1):
            print(f"\n{'='*70}")
            print(f"📌 URL {url_idx}/{len(self.scraping_urls)}: {base_url[:60]}...")
            print(f"{'='*70}")

            # Loop por cada página da URL
            for page_num in range(1, self.max_pages + 1):
                products = self.scrape_offers(base_url, page_num)

                if products:
                    pages_with_products += 1
                    print(f"   ✅ Página {page_num}: {len(products)} produtos")
                else:
                    pages_without_products += 1
                    print(f"   ⏭️  Página {page_num}: Nenhum produto")

                all_products.extend(products)

        print(f"\n{'='*70}")
        print(f"✅ SCRAPING CONCLUÍDO")
        print(f"   Total de URLs processadas: {len(self.scraping_urls)}")
        print(f"   Total de páginas processadas: {len(self.scraping_urls) * self.max_pages}")
        print(f"   Páginas com produtos: {pages_with_products}")
        print(f"   Páginas sem produtos (puladas): {pages_without_products}")
        print(f"   Total de produtos coletados: {len(all_products)}")
        print(f"{'='*70}")
        return all_products

if __name__ == "__main__":
    # Teste do scraper
    scraper = MeliScraper()
    products = scraper.scrape_all_pages()

    if products:
        print("\n Primeiros 3 produtos:")
        for i, product in enumerate(products[:3], 1):
            print(f"\n{i}. {product['product_name'][:60]}")
            print(f"   Preço: R$ {product['sale_price']:.2f}")
            print(f"   FULL: {product['is_full']}")
