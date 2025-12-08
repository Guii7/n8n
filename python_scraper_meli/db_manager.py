"""
Gerenciador de conexão com PostgreSQL (banco do n8n Docker)
"""
import os
import psycopg2
import logging
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from datetime import datetime
from zoneinfo import ZoneInfo

load_dotenv()

# Obter logger (herdará configuração de main.py)
logger = logging.getLogger(__name__)

# Timezone de Brasília (UTC-3)
BRAZIL_TZ = ZoneInfo('America/Sao_Paulo')

class DatabaseManager:
    def __init__(self):
        self.conn_params = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': os.getenv('POSTGRES_PORT', '5433'),
            'database': os.getenv('POSTGRES_DB', 'n8n_db'),
            'user': os.getenv('POSTGRES_USER', 'n8n_user'),
            'password': os.getenv('POSTGRES_PASSWORD', 'n8n_password')
        }

    def connect(self):
        """Cria uma conexão com o banco"""
        return psycopg2.connect(**self.conn_params)

    def insert_offer(self, offer_data):
        """
        Insere ou atualiza uma oferta no banco seguindo a lógica:
        1. Se oferta não existe: insere como 'new'
        2. Se oferta existe:
           a. Se preço mudou: atualiza e marca como 'new' (para reenvio)
           b. Se preço igual E foi enviada há mais de 5 dias: marca como 'new' (para reenvio)
           c. Se preço igual E foi enviada há menos de 5 dias: não faz nada

        Args:
            offer_data (dict): Dados da oferta com chaves:
                - product_name
                - original_url
                - affiliate_url (OBRIGATÓRIO - não insere se estiver vazio)
                - image_url
                - list_price
                - sale_price
                - installments_info
                - shipping_info
                - is_full

        Returns:
            bool: True se inseriu/atualizou com sucesso
        """
        conn = None
        try:
            # Validação 1: não inserir ofertas sem link afiliado
            if not offer_data.get('affiliate_url'):
                print(f"AVISO: Oferta sem link afiliado ignorada: {offer_data['product_name'][:50]}...")
                return False

            # Validação 2: URL deve começar com http (não pode ser aviso/erro)
            affiliate_url = offer_data.get('affiliate_url', '').strip()
            if not affiliate_url.startswith('http://') and not affiliate_url.startswith('https://'):
                print(f"AVISO: URL inválida (não é link): {affiliate_url[:50]}... | Produto: {offer_data['product_name'][:30]}...")
                return False

            # Validação 3: não pode ser um aviso/erro do Mercado Livre
            invalid_markers = ['⚠️', '❌', 'erro', 'error', 'não é permitido', 'não permitido', 'indisponível']
            affiliate_lower = affiliate_url.lower()
            for marker in invalid_markers:
                if marker.lower() in affiliate_lower:
                    print(f"AVISO: URL contém marcador de erro ({marker}): {affiliate_url[:50]}... | Produto: {offer_data['product_name'][:30]}...")
                    return False

            conn = self.connect()
            cursor = conn.cursor()

            # Define timezone para timestamps
            # PostgreSQL NOW() já usa UTC, mas vamos garantir que o app use hora local
            now_brazil = datetime.now(BRAZIL_TZ)

            # Converter para string ISO 8601 com timezone para o PostgreSQL armazenar corretamente
            now_str = now_brazil.isoformat()

            query = """
            INSERT INTO mercado_livre_offers (
                product_name,
                original_url,
                affiliate_url,
                image_url,
                list_price,
                sale_price,
                installments_info,
                shipping_info,
                is_full,
                status_telegram,
                created_at,
                updated_at
            )
            VALUES (
                %(product_name)s,
                %(original_url)s,
                %(affiliate_url)s,
                %(image_url)s,
                %(list_price)s,
                %(sale_price)s,
                %(installments_info)s,
                %(shipping_info)s,
                %(is_full)s,
                'new',
                %(now)s::timestamp with time zone,
                %(now)s::timestamp with time zone
            )
            ON CONFLICT (original_url)
            DO UPDATE SET
                product_name = EXCLUDED.product_name,
                affiliate_url = EXCLUDED.affiliate_url,
                image_url = EXCLUDED.image_url,
                list_price = EXCLUDED.list_price,
                sale_price = EXCLUDED.sale_price,
                installments_info = EXCLUDED.installments_info,
                shipping_info = EXCLUDED.shipping_info,
                is_full = EXCLUDED.is_full,
                updated_at = %(now)s,
                -- Marca como 'new' apenas se:
                -- 1. Preço mudou OU
                -- 2. Preço igual MAS foi enviada há mais de 5 dias
                status_telegram = CASE
                    -- Se preço mudou: marca como 'new'
                    WHEN mercado_livre_offers.sale_price IS DISTINCT FROM EXCLUDED.sale_price THEN 'new'
                    -- Se preço igual E foi enviada há mais de 5 dias: marca como 'new'
                    WHEN mercado_livre_offers.sent_at_telegram IS NOT NULL
                         AND mercado_livre_offers.sent_at_telegram < (%(now)s - INTERVAL '5 days') THEN 'new'
                    -- Caso contrário: mantém status atual
                    ELSE mercado_livre_offers.status_telegram
                END
            WHERE
                -- Só executa UPDATE se preço mudou OU se está elegível para reenvio
                mercado_livre_offers.sale_price IS DISTINCT FROM EXCLUDED.sale_price OR
                (mercado_livre_offers.sent_at_telegram IS NOT NULL
                 AND mercado_livre_offers.sent_at_telegram < (%(now)s - INTERVAL '5 days'));
            """

            cursor.execute(query, {**offer_data, 'now': now_brazil})
            conn.commit()

            # Verifica se houve insert ou update
            if cursor.rowcount > 0:
                print(f"OK: Oferta salva: {offer_data['product_name'][:50]}...")
                return True
            else:
                print(f"INFO: Oferta já existe e está atualizada: {offer_data['product_name'][:50]}...")
                return True

        except Exception as e:
            print(f"ERRO: Erro ao salvar oferta: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                cursor.close()
                conn.close()

    def get_recent_offers(self, hours=24, limit=50):
        """
        Busca ofertas recentes do banco

        Args:
            hours (int): Quantas horas atrás buscar
            limit (int): Máximo de resultados

        Returns:
            list: Lista de dicionários com dados das ofertas
        """
        conn = None
        try:
            conn = self.connect()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            query = """
            SELECT id, url, title, price, original_price, discount_percentage,
                   seller_name, seller_reputation, free_shipping, installments,
                   photos, description
            FROM mercado_livre_offers
            WHERE status_telegram = 'new'
            ORDER BY created_at DESC
            LIMIT %s
            """

            cursor.execute(query, (hours, limit))
            results = cursor.fetchall()

            return [dict(row) for row in results]

        except Exception as e:
            print(f"ERRO: Erro ao buscar ofertas: {e}")
            return []
        finally:
            if conn:
                cursor.close()
                conn.close()

    def mark_as_sent(self, offer_id: int) -> bool:
        """Marca uma oferta como enviada"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "UPDATE mercado_livre_offers SET status_telegram = 'sent', sent_at_telegram = CURRENT_TIMESTAMP WHERE id = %s",
                (offer_id,)
            )
            self.conn.commit()
            cursor.close()
            return True
        except Exception as e:
            logger.error(f"Erro ao marcar oferta {offer_id} como enviada: {e}")
            self.conn.rollback()
            return False

if __name__ == "__main__":
    # Teste de conexão
    db = DatabaseManager()
    print(" Testando conexão com banco...")

    test_offer = {
        'product_name': 'Produto Teste Python',
        'original_url': 'https://produto.mercadolivre.com.br/MLB-TEST-123',
        'affiliate_url': 'https://mercadolivre.com/sec/TEST',
        'image_url': 'https://http2.mlstatic.com/test.jpg',
        'list_price': 199.99,
        'sale_price': 99.99,
        'installments_info': 'em até 12x',
        'shipping_info': 'Frete grátis',
        'is_full': True
    }

    if db.insert_offer(test_offer):
        print("OK: Teste de inserção: OK")

        offers = db.get_recent_offers(hours=1, limit=5)
        print(f"OK: Teste de consulta: {len(offers)} ofertas encontradas")
    else:
        print("ERRO: Teste falhou")
