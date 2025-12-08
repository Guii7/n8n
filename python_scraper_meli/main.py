"""
Script principal - Orquestra scraping, geração de links e salvamento no banco
Refatorado v2: Melhor logging, validação e tratamento de erros
"""

# ⚠️ WORKAROUND CRÍTICO: Aplicar nest_asyncio ABSOLUTAMENTE NO INÍCIO
# Antes de QUALQUER outro import!!!
import sys
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    import nest_asyncio
    nest_asyncio.apply()
    print("[NEST_ASYNCIO] Aplicado MUITO CEDO")
except Exception as e:
    print(f"[NEST_ASYNCIO_ERROR] {e}")

import os
import logging
from datetime import datetime
from dotenv import load_dotenv

# Configurar encoding UTF-8 no Windows
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

load_dotenv()

# Configurar logging - GARANTIR que TUDO vai para stdout
# Remover handlers existentes
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Criar logger que imprime TUDO em stdout E arquivo
logger = logging.getLogger(__name__)
logger.handlers.clear()  # Limpar qualquer handler anterior
logger.setLevel(logging.INFO)

# Formato consistente para ambos os handlers
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# Handler para STDOUT (capture_output vai pegar isso)
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.INFO)
stdout_handler.setFormatter(formatter)
logger.addHandler(stdout_handler)

# Handler para arquivo de log
try:
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    # Arquivo com timestamp para cada execução
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"scraper_{timestamp}.log")

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    print(f"[MAIN] Logging configurado para stdout E arquivo: {log_file}")
except Exception as e:
    print(f"[MAIN] ⚠️ Erro ao configurar arquivo de log: {e}")

from scraper import MeliScraper
from link_generator import AffiliateLinkGenerator
from db_manager import DatabaseManager


def validate_environment():
    """Valida variáveis de ambiente necessárias"""
    required_vars = ['ML_EMAIL', 'ML_PASSWORD', 'POSTGRES_HOST', 'POSTGRES_DB']
    missing = []

    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)

    if missing:
        logger.error(f"Variáveis de ambiente faltando: {', '.join(missing)}")
        return False

    logger.info("✅ Variáveis de ambiente validadas")
    return True


def main():
    print("=" * 70)
    print("MERCADO LIVRE AFFILIATE SCRAPER - v2.0")
    print("=" * 70)
    print(f"Iniciado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

    logger.info("=" * 70)
    logger.info("MERCADO LIVRE AFFILIATE SCRAPER - v2.0")
    logger.info("=" * 70)
    logger.info(f"Iniciado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

    # Validar ambiente
    if not validate_environment():
        logger.error("❌ Falha na validação do ambiente")
        return 0

    try:
        # Inicializa componentes
        logger.info("\n📦 Inicializando componentes...")
        scraper = MeliScraper()
        link_gen = AffiliateLinkGenerator()
        db = DatabaseManager()
        logger.info("✅ Componentes inicializados")

    except Exception as e:
        logger.error(f"❌ Erro ao inicializar componentes: {e}", exc_info=True)
        return 0

    # ETAPA 1: Scraping
    logger.info("\n" + "=" * 70)
    logger.info("ETAPA 1: SCRAPING DE OFERTAS")
    logger.info("=" * 70)

    try:
        products = scraper.scrape_all_pages()

        if not products:
            print("❌ Nenhum produto encontrado")
            logger.error("❌ Nenhum produto encontrado")
            return 0

        print(f"✅ {len(products)} produtos coletados")
        logger.info(f"✅ {len(products)} produtos coletados")

    except Exception as e:
        logger.error(f"❌ Erro durante scraping: {e}", exc_info=True)
        return 0

    # ETAPA 2: Geração de Links Afiliados
    logger.info("\n" + "=" * 70)
    logger.info("ETAPA 2: GERAÇÃO DE LINKS AFILIADOS")
    logger.info("=" * 70)

    try:
        # Coleta URLs dos produtos
        product_urls = [p['original_url'] for p in products]
        print(f"📝 {len(product_urls)} URLs para processar")
        logger.info(f"📝 {len(product_urls)} URLs para processar")

        # Gera links (com sessão persistente do Windows)
        affiliate_links = link_gen.generate_batch(product_urls)

        if not affiliate_links:
            print("❌ Nenhum link afiliado gerado")
            logger.error("❌ Nenhum link afiliado gerado")
            return 0

        print(f"✅ {len(affiliate_links)} links afiliados gerados")
        logger.info(f"✅ {len(affiliate_links)} links afiliados gerados")

    except Exception as e:
        logger.error(f"❌ Erro ao gerar links: {e}", exc_info=True)
        return 0

    # ETAPA 3: Salvar no Banco
    logger.info("\n" + "=" * 70)
    logger.info("ETAPA 3: SALVANDO NO BANCO DE DADOS")
    logger.info("=" * 70)

    saved_count = 0
    skipped_no_link = 0
    updated_count = 0
    failed_count = 0

    try:
        for idx, product in enumerate(products, 1):
            original_url = product['original_url']

            # REGRA: Só salva produtos com link afiliado
            if original_url not in affiliate_links:
                logger.debug(f"[{idx}/{len(products)}] ⏭️ Pulando (sem link): {product['product_name'][:40]}...")
                skipped_no_link += 1
                continue

            # Adiciona link afiliado
            product['affiliate_url'] = affiliate_links[original_url]

            # Salva no banco
            if db.insert_offer(product):
                saved_count += 1
                logger.debug(f"[{idx}/{len(products)}] ✅ Salvo: {product['product_name'][:40]}...")
            else:
                failed_count += 1
                logger.debug(f"[{idx}/{len(products)}] ❌ Falha: {product['product_name'][:40]}...")

        logger.info(f"✅ Banco de dados atualizado")

    except Exception as e:
        logger.error(f"❌ Erro ao salvar no banco: {e}", exc_info=True)
        return 0

    # RESUMO
    print("\n" + "=" * 70)
    print("RESUMO DA EXECUÇÃO")
    print("=" * 70)
    print(f"Produtos coletados: {len(products)}")
    print(f"Links afiliados gerados: {len(affiliate_links)}")
    print(f"Salvos no banco: {saved_count}")
    print(f"Pulados (sem link): {skipped_no_link}")
    print(f"Falhas: {failed_count}")
    print(f"Finalizado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 70 + "\n")

    logger.info("\n" + "=" * 70)
    logger.info("RESUMO DA EXECUÇÃO")
    logger.info("=" * 70)
    logger.info(f"Produtos coletados: {len(products)}")
    logger.info(f"Links afiliados gerados: {len(affiliate_links)}")
    logger.info(f"Salvos no banco: {saved_count}")
    logger.info(f"Pulados (sem link): {skipped_no_link}")
    logger.info(f"Falhas: {failed_count}")
    logger.info(f"Finalizado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    logger.info("=" * 70 + "\n")

    return saved_count


if __name__ == "__main__":
    try:
        result = main()

        logger.info(f"🔍 [DEBUG] main() retornou: {result} (tipo: {type(result).__name__})")

        # Exit code: 0 = sucesso, 1 = erro
        if result and result > 0:
            logger.info(f"✅ Execução concluída com sucesso (result={result})")
            print(f"✅ Execução concluída com sucesso (result={result})")
            sys.exit(0)
        else:
            logger.error(f"❌ Execução falhou (result={result})")
            print(f"❌ Execução falhou (result={result})")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.warning("\n\n⚠️ Execução interrompida pelo usuário")
        sys.exit(1)

    except Exception as e:
        logger.error(f"\n❌ ERRO FATAL: {e}", exc_info=True)
        sys.exit(1)

