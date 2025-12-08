"""
Gerenciador de conexão com PostgreSQL para Amazon Offers
Baseado no db_manager do Mercado Livre, adaptado para Amazon

LÓGICA DE DUPLICAÇÃO (chave: URL_BASE + sale_price):
- URL_BASE = tudo antes do "?" na original_url
- Se URL_BASE igual e sale_price igual → IGNORAR (não faz nada)
- Se URL_BASE igual e sale_price diferente → ATUALIZAR status_* para "new",
  limpar sent_at_* e atualizar updated_at
- Se URL_BASE não existe → INSERIR novo registro
"""
import os
import psycopg2
import logging
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlparse, urlunparse

load_dotenv()

logger = logging.getLogger(__name__)

# Timezone de Brasília (UTC-3)
BRAZIL_TZ = ZoneInfo('America/Sao_Paulo')


def get_base_url(url):
    """
    Extrai a URL base (antes do ?) para usar como chave de identificação.
    Ex: https://www.amazon.com.br/Apple-iPhone-15-128-GB/dp/B0CP6CVJSG?ref=...
    -> https://www.amazon.com.br/Apple-iPhone-15-128-GB/dp/B0CP6CVJSG
    """
    if not url:
        return url
    parsed = urlparse(url)
    # Reconstruir sem query string e fragment
    base = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
    return base


class AmazonDatabaseManager:
    def __init__(self):
        self.conn_params = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': os.getenv('POSTGRES_PORT', '5432'),
            'database': os.getenv('POSTGRES_DB', 'n8n'),
            'user': os.getenv('POSTGRES_USER', 'n8n_user'),
            'password': os.getenv('POSTGRES_PASSWORD', '')
        }

    def connect(self):
        """Cria uma conexão com o banco"""
        return psycopg2.connect(**self.conn_params)

    def _normalize_url(self, url):
        """Normaliza URL para comparação (remove query params)"""
        return get_base_url(url)

    def insert_offer(self, offer_data):
        """
        Insere ou atualiza uma oferta no banco seguindo a lógica:

        CHAVE DE IDENTIFICAÇÃO: URL_BASE (sem query params)

        1. Se URL_BASE não existe: INSERIR novo registro
        2. Se URL_BASE existe:
           a. Se sale_price igual ao do banco → IGNORAR (não faz nada)
           b. Se sale_price diferente → ATUALIZAR:
              - status_telegram, status_whatsapp, status_tiktok = 'new'
              - sent_at_telegram, sent_at_whatsapp, sent_at_tiktok = NULL
              - updated_at = NOW()
              - Atualizar demais campos

        Args:
            offer_data (dict): Dados da oferta com chaves:
                - product_name
                - original_url (OBRIGATÓRIO - chave única via URL_BASE)
                - affiliate_url (OBRIGATÓRIO - não insere se estiver vazio)
                - image_url
                - asin
                - list_price (preço original)
                - sale_price (preço promocional)
                - discount_percentage
                - has_coupon
                - coupon_code
                - coupon_discount
                - promotion_text (múltiplas promoções separadas por |||)
                - prime_eligible
                - shipping_info
                - installment_info
                - rating
                - review_count
                - category
                - source_url
                - scrape_type

        Returns:
            str: 'inserted', 'updated', 'ignored', ou 'error'
        """
        conn = None
        try:
            # Validação 1: não inserir ofertas sem link afiliado
            if not offer_data.get('affiliate_url'):
                logger.warning(f"Oferta sem link afiliado ignorada: {offer_data['product_name'][:50]}...")
                return 'error'

            # Validação 2: URL deve começar com http
            affiliate_url = offer_data.get('affiliate_url', '').strip()
            if not affiliate_url.startswith('http://') and not affiliate_url.startswith('https://'):
                logger.warning(f"URL inválida (não é link): {affiliate_url[:50]}... | Produto: {offer_data['product_name'][:30]}...")
                return 'error'

            # Validação 3: não pode ser um aviso/erro
            invalid_markers = ['⚠️', '❌', 'erro', 'error', 'não é permitido', 'não permitido', 'indisponível']
            affiliate_lower = affiliate_url.lower()
            for marker in invalid_markers:
                if marker.lower() in affiliate_lower:
                    logger.warning(f"URL contém marcador de erro ({marker}): {affiliate_url[:50]}... | Produto: {offer_data['product_name'][:30]}...")
                    return 'error'

            conn = self.connect()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Hora atual no timezone do Brasil
            now_brazil = datetime.now(BRAZIL_TZ)

            # Normalizar URL para comparação (URL_BASE = sem query params)
            url_base = self._normalize_url(offer_data.get('original_url', ''))
            sale_price = offer_data.get('sale_price')

            # Verificar se produto já existe (buscar por URL_BASE)
            check_query = """
                SELECT id, sale_price,
                       SPLIT_PART(original_url, '?', 1) as url_base
                FROM amazon_offers
                WHERE SPLIT_PART(original_url, '?', 1) = %s
                LIMIT 1
            """
            cursor.execute(check_query, (url_base,))
            existing = cursor.fetchone()

            if existing:
                # Produto já existe - verificar se preço mudou
                existing_price = float(existing['sale_price']) if existing['sale_price'] else None
                new_price = float(sale_price) if sale_price else None

                if existing_price == new_price:
                    # Preço igual → IGNORAR
                    logger.info(f"  ⏭️ IGNORADO (mesmo preço R${existing_price}): {offer_data['product_name'][:40]}...")
                    return 'ignored'
                else:
                    # Preço diferente → ATUALIZAR com status "new"
                    logger.info(f"  🔄 Preço alterado! R${existing_price} → R${new_price}")

                    update_query = """
                        UPDATE amazon_offers SET
                            product_name = %(product_name)s,
                            affiliate_url = %(affiliate_url)s,
                            image_url = %(image_url)s,
                            asin = %(asin)s,
                            list_price = %(list_price)s,
                            sale_price = %(sale_price)s,
                            discount_percentage = %(discount_percentage)s,
                            has_coupon = %(has_coupon)s,
                            coupon_code = %(coupon_code)s,
                            coupon_discount = %(coupon_discount)s,
                            promotion_text = %(promotion_text)s,
                            prime_eligible = %(prime_eligible)s,
                            shipping_info = %(shipping_info)s,
                            installment_info = %(installment_info)s,
                            rating = %(rating)s,
                            review_count = %(review_count)s,
                            category = %(category)s,
                            source_url = %(source_url)s,
                            scrape_type = %(scrape_type)s,
                            -- Resetar status para reenvio
                            status_telegram = 'new',
                            status_whatsapp = 'new',
                            status_tiktok = 'new',
                            sent_at_telegram = NULL,
                            sent_at_whatsapp = NULL,
                            sent_at_tiktok = NULL,
                            updated_at = %(now)s
                        WHERE id = %(existing_id)s
                    """

                    params = self._build_offer_params(offer_data, now_brazil)
                    params['existing_id'] = existing['id']

                    cursor.execute(update_query, params)
                    conn.commit()

                    logger.info(f"✅ Oferta ATUALIZADA (preço alterado): {offer_data['product_name'][:50]}...")
                    return 'updated'
            else:
                # Produto não existe → INSERIR
                insert_query = """
                    INSERT INTO amazon_offers (
                        product_name,
                        original_url,
                        affiliate_url,
                        image_url,
                        asin,
                        list_price,
                        sale_price,
                        discount_percentage,
                        has_coupon,
                        coupon_code,
                        coupon_discount,
                        promotion_text,
                        prime_eligible,
                        shipping_info,
                        installment_info,
                        rating,
                        review_count,
                        category,
                        source_url,
                        scrape_type,
                        status_telegram,
                        status_whatsapp,
                        status_tiktok,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        %(product_name)s,
                        %(original_url)s,
                        %(affiliate_url)s,
                        %(image_url)s,
                        %(asin)s,
                        %(list_price)s,
                        %(sale_price)s,
                        %(discount_percentage)s,
                        %(has_coupon)s,
                        %(coupon_code)s,
                        %(coupon_discount)s,
                        %(promotion_text)s,
                        %(prime_eligible)s,
                        %(shipping_info)s,
                        %(installment_info)s,
                        %(rating)s,
                        %(review_count)s,
                        %(category)s,
                        %(source_url)s,
                        %(scrape_type)s,
                        'new',
                        'new',
                        'new',
                        %(now)s,
                        %(now)s
                    )
                """

                params = self._build_offer_params(offer_data, now_brazil)
                cursor.execute(insert_query, params)
                conn.commit()

                logger.info(f"✅ Oferta INSERIDA: {offer_data['product_name'][:50]}...")
                return 'inserted'

        except psycopg2.Error as e:
            logger.error(f"❌ Erro ao inserir oferta no banco: {e}")
            if conn:
                conn.rollback()
            return 'error'

        except Exception as e:
            logger.error(f"❌ Erro inesperado ao salvar oferta: {e}")
            import traceback
            traceback.print_exc()
            if conn:
                conn.rollback()
            return 'error'

        finally:
            if conn:
                cursor.close()
                conn.close()

    def _build_offer_params(self, offer_data, now_brazil):
        """Constrói dicionário de parâmetros para INSERT/UPDATE"""
        return {
            'product_name': offer_data.get('product_name', ''),
            'original_url': offer_data.get('original_url', ''),
            'affiliate_url': offer_data.get('affiliate_url', ''),
            'image_url': offer_data.get('image_url'),
            'asin': offer_data.get('asin'),
            'list_price': offer_data.get('list_price'),
            'sale_price': offer_data.get('sale_price'),
            'discount_percentage': offer_data.get('discount_percentage'),
            'has_coupon': offer_data.get('has_coupon', False),
            'coupon_code': offer_data.get('coupon_code'),
            'coupon_discount': offer_data.get('coupon_discount'),
            'promotion_text': offer_data.get('promotion_text'),
            'prime_eligible': offer_data.get('prime_eligible', False),
            'shipping_info': offer_data.get('shipping_info'),
            'installment_info': offer_data.get('installment_info'),
            'rating': offer_data.get('rating'),
            'review_count': offer_data.get('review_count'),
            'category': offer_data.get('category'),
            'source_url': offer_data.get('source_url'),
            'scrape_type': offer_data.get('scrape_type', 'product'),
            'now': now_brazil
        }

    def get_offers_to_send(self, channel='telegram', limit=10):
        """
        Busca ofertas pendentes de envio para um canal específico

        Args:
            channel (str): Canal de envio ('telegram', 'whatsapp', 'tiktok')
            limit (int): Número máximo de ofertas a retornar

        Returns:
            list: Lista de dicionários com dados das ofertas
        """
        conn = None
        try:
            conn = self.connect()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            status_column = f"status_{channel}"

            query = f"""
            SELECT *
            FROM amazon_offers
            WHERE {status_column} = 'new'
            ORDER BY created_at DESC
            LIMIT %s
            """

            cursor.execute(query, (limit,))
            offers = cursor.fetchall()

            logger.info(f"📊 Encontradas {len(offers)} ofertas pendentes para {channel}")
            return offers

        except psycopg2.Error as e:
            logger.error(f"❌ Erro ao buscar ofertas: {e}")
            return []

        finally:
            if conn:
                cursor.close()
                conn.close()

    def mark_as_sent(self, offer_id, channel='telegram'):
        """
        Marca uma oferta como enviada em um canal específico

        Args:
            offer_id (int): ID da oferta
            channel (str): Canal de envio ('telegram', 'whatsapp', 'tiktok')

        Returns:
            bool: True se atualizou com sucesso
        """
        conn = None
        try:
            conn = self.connect()
            cursor = conn.cursor()

            now_brazil = datetime.now(BRAZIL_TZ)

            status_column = f"status_{channel}"
            sent_at_column = f"sent_at_{channel}"

            query = f"""
            UPDATE amazon_offers
            SET {status_column} = 'sent',
                {sent_at_column} = %s
            WHERE id = %s
            """

            cursor.execute(query, (now_brazil, offer_id))
            conn.commit()

            logger.info(f"✅ Oferta {offer_id} marcada como enviada em {channel}")
            return True

        except psycopg2.Error as e:
            logger.error(f"❌ Erro ao marcar oferta como enviada: {e}")
            if conn:
                conn.rollback()
            return False

        finally:
            if conn:
                cursor.close()
                conn.close()

    def test_connection(self):
        """Testa conexão com o banco de dados"""
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version = cursor.fetchone()
            logger.info(f"✅ Conexão com banco OK: {version[0]}")
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao conectar ao banco: {e}")
            return False
