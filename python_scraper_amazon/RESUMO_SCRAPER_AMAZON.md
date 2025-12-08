# Amazon Scraper - Resumo Técnico Completo

> Gerado em: 28/11/2025
> Versão: 2.0 (com paginação URL e captura de dados detalhados)

---

## 📁 Estrutura do Projeto

```
python_scraper_amazon/
├── scraper.py              # Lógica principal de scraping
├── db_manager.py           # Gerenciamento do PostgreSQL
├── capture_session.py      # Captura de sessão Amazon/SiteStripe
├── config.yml              # Configurações (URLs, seletores, delays)
├── session_data.json       # Cookies da sessão Amazon (gerado)
├── venv/                   # Ambiente virtual Python
├── logs/                   # Logs de execução
└── requirements.txt        # Dependências Python
```

---

## 🗄️ Estrutura do Banco de Dados

### Tabela: `amazon_offers`

**Conexão:**
- Host: `localhost` (Docker)
- Port: `5432`
- Database: `n8n`
- User: `n8n_user`
- Password: `B3rn4rd0`
- Container: `n8n_postgres_db`

**Colunas:**

| Coluna | Tipo | Nullable | Default | Descrição |
|--------|------|----------|---------|-----------|
| `id` | INTEGER | NOT NULL | SERIAL | ID único auto-incremento |
| `product_name` | VARCHAR(512) | NOT NULL | - | Nome do produto |
| `original_url` | TEXT | NOT NULL | - | URL original do produto (UNIQUE) |
| `affiliate_url` | TEXT | - | - | Link de afiliado (amzn.to/xxx) |
| `image_url` | TEXT | - | - | URL da imagem do produto |
| `asin` | VARCHAR(20) | - | - | ASIN da Amazon |
| `list_price` | NUMERIC(10,2) | - | - | Preço original (riscado/"De:") |
| `sale_price` | NUMERIC(10,2) | - | - | Preço promocional atual |
| `discount_percentage` | INTEGER | - | - | Percentual de desconto |
| `has_coupon` | BOOLEAN | - | FALSE | Tem cupom disponível |
| `coupon_code` | VARCHAR(100) | - | - | Código do cupom |
| `coupon_discount` | NUMERIC(10,2) | - | - | Valor do desconto do cupom |
| `promotion_text` | VARCHAR(255) | - | - | Textos de promoção (separados por `\|\|\|`) |
| `prime_eligible` | BOOLEAN | - | FALSE | Elegível para Prime |
| `shipping_info` | VARCHAR(255) | - | - | Info de frete (ex: "GRÁTIS - Terça-feira, 2 de Dezembro") |
| `installment_info` | VARCHAR(255) | - | - | Info parcelamento (ex: "12x de R$ 332,49 sem juros") |
| `rating` | NUMERIC(2,1) | - | - | Avaliação (1.0 - 5.0) |
| `review_count` | INTEGER | - | - | Quantidade de avaliações |
| `category` | VARCHAR(255) | - | - | Categoria do produto |
| `source_url` | TEXT | - | - | URL da página de listagem |
| `scrape_type` | VARCHAR(50) | - | 'product' | Tipo de scraping |
| `status_telegram` | VARCHAR(20) | - | 'new' | Status de envio Telegram |
| `sent_at_telegram` | TIMESTAMP TZ | - | - | Data/hora envio Telegram |
| `error_status_telegram` | VARCHAR(255) | - | - | Erro de envio Telegram |
| `error_at_telegram` | TIMESTAMP TZ | - | - | Data/hora do erro |
| `status_whatsapp` | VARCHAR(20) | - | 'new' | Status de envio WhatsApp |
| `sent_at_whatsapp` | TIMESTAMP TZ | - | - | Data/hora envio WhatsApp |
| `error_status_whatsapp` | VARCHAR(255) | - | - | Erro de envio WhatsApp |
| `error_at_whatsapp` | TIMESTAMP TZ | - | - | Data/hora do erro |
| `status_tiktok` | VARCHAR(20) | - | 'new' | Status de envio TikTok |
| `sent_at_tiktok` | TIMESTAMP TZ | - | - | Data/hora envio TikTok |
| `error_status_tiktok` | VARCHAR(255) | - | - | Erro de envio TikTok |
| `error_at_tiktok` | TIMESTAMP TZ | - | - | Data/hora do erro |
| `created_at` | TIMESTAMP TZ | - | CURRENT_TIMESTAMP | Data de criação |
| `updated_at` | TIMESTAMP TZ | - | CURRENT_TIMESTAMP | Data de atualização |

**Índices:**
- `amazon_offers_pkey` - PRIMARY KEY (id)
- `amazon_offers_original_url_key` - UNIQUE (original_url)
- `idx_amazon_offers_asin` - btree (asin)
- `idx_amazon_offers_created_at` - btree (created_at)
- `idx_amazon_offers_scrape_type` - btree (scrape_type)
- `idx_amazon_offers_sent_at_telegram` - btree (sent_at_telegram)
- `idx_amazon_offers_status_telegram` - btree (status_telegram)
- `idx_amazon_offers_status_tiktok` - btree (status_tiktok)
- `idx_amazon_offers_status_whatsapp` - btree (status_whatsapp)

---

## 🔄 Lógica de Deduplicação e Atualização

### Chave Única de Identificação
```
URL_BASE = tudo antes do "?" na original_url
Exemplo: https://www.amazon.com.br/Apple-iPhone-15-128-GB/dp/B0CP6CVJSG
```

### Fluxo de Decisão ao Inserir

```
┌─────────────────────────────────────────────────────┐
│ Novo produto coletado com sale_price = X            │
└─────────────────────┬───────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────┐
│ Busca no DB por URL_BASE                            │
│ SELECT * WHERE SPLIT_PART(original_url, '?', 1) = ? │
└─────────────────────┬───────────────────────────────┘
                      ▼
              ┌───────┴───────┐
              │   Existe?     │
              └───────┬───────┘
         NÃO  ◄───────┴───────► SIM
              ▼                     ▼
     ┌────────────────┐    ┌──────────────────────┐
     │  INSERIR novo  │    │ Comparar sale_price  │
     │  registro      │    │ do banco com o novo  │
     └────────────────┘    └──────────┬───────────┘
                                      ▼
                         ┌────────────┴────────────┐
                         │ Preço igual?            │
                         └────────────┬────────────┘
                    SIM  ◄────────────┴────────────► NÃO
                         ▼                              ▼
              ┌─────────────────┐         ┌─────────────────────────────┐
              │    IGNORAR      │         │        ATUALIZAR            │
              │ (retorna        │         │ - Todos os campos           │
              │  'ignored')     │         │ - status_* = 'new'          │
              └─────────────────┘         │ - sent_at_* = NULL          │
                                          │ - updated_at = NOW()        │
                                          │ (retorna 'updated')         │
                                          └─────────────────────────────┘
```

### Valores de Retorno do `insert_offer()`
- `'inserted'` - Produto novo inserido
- `'updated'` - Produto existente atualizado (preço mudou)
- `'ignored'` - Produto existe com mesmo preço
- `'error'` - Erro de validação ou banco

---

## 🔍 Lógica de Scraping

### 1. Paginação (Black Friday)

A Amazon usa paginação virtual com parâmetros na URL:
```
https://www.amazon.com.br/blackfriday?promotionsSearchStartIndex=X&promotionsSearchPageSize=60
```

- `promotionsSearchStartIndex`: Incrementa de 30 em 30
- `promotionsSearchPageSize`: Sempre 60

O scraper navega por múltiplas páginas até atingir o limite configurado.

### 2. Coleta de Produtos

Para cada página:
1. Navega para URL com parâmetros de paginação
2. Faz scroll para carregar produtos (virtualização)
3. Coleta `div[data-testid="product-card"]`
4. Extrai dados básicos do card

### 3. Geração de Link de Afiliado (SiteStripe)

Para cada produto:
1. Abre página do produto
2. Aguarda SiteStripe carregar (barra de afiliado da Amazon)
3. **Captura dados detalhados** (preço, parcelamento, frete, promoções)
4. Clica em "Obter link" do SiteStripe
5. Lê link do textarea (NÃO usa clipboard!)
6. Retorna link `amzn.to/xxx`

### 4. Seletores CSS Importantes

**Dados do Produto (página individual):**
```css
/* Preço promocional */
span.priceToPay span.a-price-whole     /* parte inteira: "3869" */
span.priceToPay span.a-price-fraction  /* centavos: "10" */

/* Preço original (riscado) */
span.a-price.a-text-price[data-a-strike="true"] span.a-offscreen

/* Parcelamento */
#best-offer-string-cc

/* Frete */
span[data-csa-c-delivery-price]        /* atributos: data-csa-c-delivery-price, data-csa-c-delivery-time */

/* Promoções */
span.promoPriceBlockMessage            /* múltiplas, juntadas com ||| */
```

**SiteStripe:**
```css
#amzn-ss-get-link-button     /* Botão "Obter link" */
#amzn-ss-text-shortlink-textarea  /* Textarea com link gerado */
```

---

## ⚙️ Configuração (config.yml)

### URLs de Scraping
```yaml
scraping_configs:
  - name: "Black Friday Amazon"
    url: "https://www.amazon.com.br/blackfriday"
    type: "product"
    max_offers: 240
    enabled: true
```

### Delays (segundos)
```yaml
delays:
  between_products: 1
  between_pages: 3
  after_login: 3
  sitestripe_load: 2
```

### Timeouts (milissegundos)
```yaml
timeouts:
  page_load: 30000
  element_wait: 10000
  sitestripe_wait: 5000
```

---

## 🚀 Como Executar

### 1. Primeira vez (capturar sessão)
```bash
cd python_scraper_amazon
.\venv\Scripts\activate
python capture_session.py
# Faça login manualmente no navegador que abrir
# A sessão será salva em session_data.json
```

### 2. Executar scraping
```bash
.\venv\Scripts\python.exe -m scraper
```

### 3. Verificar banco
```sql
-- Ver ofertas
SELECT id, product_name, sale_price, list_price, status_telegram
FROM amazon_offers
ORDER BY created_at DESC
LIMIT 10;

-- Ver ofertas pendentes de envio
SELECT * FROM amazon_offers
WHERE status_telegram = 'new';
```

---

## 📊 Estatísticas do Relatório

O scraper exibe:
- URLs processadas
- Produtos encontrados (total coletado)
- Produtos INSERIDOS (novos)
- Produtos ATUALIZADOS (preço mudou)
- Produtos IGNORADOS (mesmo preço)
- Erros

---

## 🔗 Integração com N8N

### Query para buscar ofertas não enviadas:
```sql
SELECT * FROM amazon_offers
WHERE status_telegram = 'new'
ORDER BY created_at DESC;
```

### Query para marcar como enviado:
```sql
UPDATE amazon_offers
SET status_telegram = 'sent',
    sent_at_telegram = NOW()
WHERE id = ?;
```

### Query para marcar erro:
```sql
UPDATE amazon_offers
SET status_telegram = 'error',
    error_status_telegram = 'Mensagem de erro',
    error_at_telegram = NOW()
WHERE id = ?;
```

---

## 🛠️ Dependências Python

```
playwright>=1.51.0
psycopg2-binary>=2.9.9
python-dotenv>=1.0.0
pyyaml>=6.0.1
```

---

## 📝 Notas Importantes

1. **Não usa clipboard** - O link de afiliado é lido diretamente do textarea via Playwright
2. **Sessão persistente** - Cookies salvos em `session_data.json`
3. **Deduplicação inteligente** - Só atualiza se preço mudou
4. **Múltiplas promoções** - Separadas por `|||` no campo `promotion_text`
5. **Timezone Brasil** - Todas as datas em `America/Sao_Paulo`
