# 📦 RESUMO COMPLETO - SCRAPER MERCADO LIVRE

**Data de Criação:** 28/11/2025
**Versão:** 2.0
**Caminho:** `C:\Users\guii7\bear_cave_labs\n8n\python_scraper_meli`

---

## 🎯 OBJETIVO DO SCRAPER

Extrair ofertas promocionais do Mercado Livre (ofertas relâmpago e promoções), gerar links de afiliado automaticamente através do LinkBuilder do ML, e salvar tudo no PostgreSQL para posterior envio via Telegram.

---

## 📁 ESTRUTURA DE ARQUIVOS

```
python_scraper_meli/
├── main.py                 # Orquestrador principal
├── scraper.py              # Extração de produtos (BeautifulSoup)
├── link_generator.py       # Geração de links afiliados (Playwright)
├── db_manager.py           # Gerenciamento PostgreSQL
├── login_session.py        # Criação de sessão persistente
├── telegram_notifier.py    # Notificações Telegram
├── config.yml              # Cloudflare Tunnel config
├── .env                    # Variáveis de ambiente
├── requirements.txt        # Dependências Python
└── venv/                   # Ambiente virtual Python
```

---

## 🗄️ ESTRUTURA DO BANCO DE DADOS

**Servidor PostgreSQL:**
- **Container Docker:** `n8n_postgres_db`
- **Host:** `localhost`
- **Porta:** `5432`
- **Database:** `n8n`
- **Usuário:** `n8n_user`
- **Senha:** `B3rn4rd0`

### Tabela: `mercado_livre_offers`

```sql
CREATE TABLE IF NOT EXISTS mercado_livre_offers (
    id                  SERIAL PRIMARY KEY,
    product_name        TEXT NOT NULL,
    original_url        TEXT UNIQUE NOT NULL,       -- Constraint UNIQUE para deduplicação
    affiliate_url       TEXT NOT NULL,
    image_url           TEXT,
    list_price          DECIMAL(10,2),              -- Preço original (De:)
    sale_price          DECIMAL(10,2),              -- Preço promocional (Por:)
    installments_info   TEXT,                       -- Ex: "em até 12x sem juros"
    shipping_info       TEXT,                       -- Ex: "Frete grátis"
    is_full             BOOLEAN DEFAULT FALSE,      -- Se é entrega FULL
    status_telegram     VARCHAR(20) DEFAULT 'new',  -- 'new', 'sent', 'error'
    sent_at_telegram    TIMESTAMP WITH TIME ZONE,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_meli_status_telegram ON mercado_livre_offers(status_telegram);
CREATE INDEX IF NOT EXISTS idx_meli_created_at ON mercado_livre_offers(created_at);
CREATE INDEX IF NOT EXISTS idx_meli_original_url ON mercado_livre_offers(original_url);
```

---

## 🔄 FLUXO DE EXECUÇÃO

```
┌─────────────────────────────────────────────────────────────────┐
│                        MAIN.PY                                   │
│ ┌─────────────────┐  ┌──────────────────┐  ┌─────────────────┐  │
│ │    SCRAPER.PY   │→ │ LINK_GENERATOR.PY │→ │  DB_MANAGER.PY  │  │
│ │  (BeautifulSoup)│  │   (Playwright)    │  │   (PostgreSQL)  │  │
│ └─────────────────┘  └──────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                           ↓
                    ┌──────────────┐
                    │  TELEGRAM    │
                    │ (via n8n)    │
                    └──────────────┘
```

### Etapas Detalhadas:

1. **ETAPA 1 - Scraping (scraper.py)**
   - Carrega URLs do `.env` (SCRAPING_URLS)
   - Para cada URL, faz MAX_PAGES requisições
   - Usa Playwright em modo headless=True
   - Extrai produtos com BeautifulSoup
   - Retorna lista de dicts com dados dos produtos

2. **ETAPA 2 - Geração de Links (link_generator.py)**
   - Recebe lista de URLs originais
   - Abre navegador com sessão persistente (já logada no ML)
   - Acessa `https://www.mercadolivre.com.br/affiliates/linkbuilder`
   - Processa URLs em lotes de LINKS_PER_BATCH (padrão: 30)
   - Retorna dict {url_original: link_afiliado}

3. **ETAPA 3 - Salvamento (db_manager.py)**
   - Para cada produto com link afiliado
   - Usa INSERT ON CONFLICT para deduplicação
   - Marca como 'new' para reenvio se preço mudou

---

## 🔧 CONFIGURAÇÕES (.env)

```env
# Credenciais Mercado Livre
ML_EMAIL=email@gmail.com
ML_PASSWORD=senha

# PostgreSQL (Docker n8n)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=n8n
POSTGRES_USER=n8n_user
POSTGRES_PASSWORD=B3rn4rd0

# Configurações do Navegador
HEADLESS=False           # False = mostra navegador (requerido para ML detectar headless)
BROWSER_WINDOW_HIDDEN=True  # True = janela posicionada fora da tela (-2400,-2400)
MAX_PAGES=5              # Páginas por URL

# Sessão Persistente (CAMINHO ABSOLUTO OBRIGATÓRIO)
SESSION_DIR=C:\Users\guii7\bear_cave_labs\puppeteer_session

# Otimização de Links
LINKS_PER_BATCH=30       # URLs processadas simultaneamente
LINK_GENERATION_WAIT_TIME=10  # Segundos base para gerar links

# URLs de Scraping (separadas por vírgula)
SCRAPING_URLS=https://www.mercadolivre.com.br/ofertas?promotion_type=lightning,...

# Telegram (2 bots)
TELEGRAM_CHAT_ID=289679283
TELEGRAM_BOT_TOKEN_SUCCESS=8084...
TELEGRAM_BOT_TOKEN_ERROR=8299...
```

---

## 🔍 SELETORES CSS UTILIZADOS

### scraper.py (BeautifulSoup)

| Elemento | Seletor | Descrição |
|----------|---------|-----------|
| Card do Produto | `div.poly-card--grid-card` | Container principal do produto |
| Título/Link | `a.poly-component__title` | Nome e URL do produto |
| Imagem | `img.poly-component__picture` | URL da imagem (data-src ou src) |
| Preço Original | `s.andes-money-amount--previous` | Preço "De:" riscado |
| Preço Promocional | `span.andes-money-amount--cents-superscript` | Preço "Por:" |
| Parcelamento | `span.poly-price__installments` | Ex: "em até 12x" |
| Frete | `div.poly-component__shipping` | Info de entrega |
| FULL | `svg.poly-shipping__promise-icon--full` | Ícone FULL |

### link_generator.py (Playwright)

| Elemento | Seletor | Descrição |
|----------|---------|-----------|
| Textarea Input | `textarea.andes-form-control__field` | Campo para colar URLs |
| Botão Gerar | `button.andes-button--loud` | Botão "Gerar Links" |
| Textarea Output | `textarea.andes-form-control__field` (2ª) | Campo com links gerados |

---

## 🔄 LÓGICA DE DEDUPLICAÇÃO

O `db_manager.py` usa **INSERT ON CONFLICT** com a seguinte lógica:

```sql
ON CONFLICT (original_url)
DO UPDATE SET
    -- Atualiza dados básicos sempre
    product_name = EXCLUDED.product_name,
    affiliate_url = EXCLUDED.affiliate_url,
    ...
    -- Marca como 'new' apenas se:
    status_telegram = CASE
        -- 1. Preço mudou: marca como 'new' (vai reenviar)
        WHEN mercado_livre_offers.sale_price IS DISTINCT FROM EXCLUDED.sale_price THEN 'new'

        -- 2. Preço igual MAS foi enviada há mais de 5 dias: marca como 'new'
        WHEN mercado_livre_offers.sent_at_telegram IS NOT NULL
             AND mercado_livre_offers.sent_at_telegram < (NOW() - INTERVAL '5 days') THEN 'new'

        -- 3. Caso contrário: mantém status atual
        ELSE mercado_livre_offers.status_telegram
    END
WHERE
    -- Só executa UPDATE se preço mudou OU elegível para reenvio
    mercado_livre_offers.sale_price IS DISTINCT FROM EXCLUDED.sale_price OR
    (mercado_livre_offers.sent_at_telegram IS NOT NULL
     AND mercado_livre_offers.sent_at_telegram < (NOW() - INTERVAL '5 days'));
```

### Resumo da Lógica:

| Cenário | Ação |
|---------|------|
| Produto novo (URL não existe) | INSERT com status='new' |
| Produto existe + preço mudou | UPDATE + status='new' |
| Produto existe + preço igual + enviado há >5 dias | UPDATE + status='new' |
| Produto existe + preço igual + enviado há <5 dias | IGNORA (não faz nada) |

---

## 🛡️ VALIDAÇÕES DE SEGURANÇA

O `db_manager.py` valida links afiliados antes de salvar:

```python
# Validação 1: Não salva se affiliate_url estiver vazio
if not offer_data.get('affiliate_url'):
    return False

# Validação 2: URL deve começar com http
if not affiliate_url.startswith('http://') and not affiliate_url.startswith('https://'):
    return False

# Validação 3: Rejeita se contiver marcadores de erro
invalid_markers = ['⚠️', '❌', 'erro', 'error', 'não é permitido', 'indisponível']
```

---

## 🎭 SESSÃO PERSISTENTE

O ML detecta automação via headless. A solução é usar **sessão persistente**:

### login_session.py

1. Abre navegador com `launch_persistent_context()`
2. Salva cookies/sessão em `SESSION_DIR`
3. Usuário faz login manual UMA VEZ
4. Sessão persiste para próximas execuções

### Configuração Anti-Foco (link_generator.py)

```python
browser = p.chromium.launch_persistent_context(
    session_dir,
    headless=False,
    args=[
        '--disable-blink-features=AutomationControlled',
        '--no-sandbox',
        '--disable-infobars',
        '--disable-notifications',
        '--disable-popup-blocking',

        # FLAGS ANTI-FOCO (não rouba teclado/mouse)
        '--disable-focus-stealing-prevention',
        '--disable-extensions',
        '--disable-plugins',
        '--disable-background-networking',
        '--disable-background-timer-throttling',
        '--disable-renderer-backgrounding',
        '--no-first-run',
        '--disable-default-apps',
        '--disable-sync',
        '--disable-translate',
        '--mute-audio'
    ],
    slow_mo=100,
    viewport={'width': 1200, 'height': 800},
    # POSICIONA JANELA FORA DA TELA
    **({'window_position': {'x': -2400, 'y': -2400}} if browser_window_hidden else {})
)
```

---

## 📊 EXTRAÇÃO DE DADOS (scraper.py)

### Método `_parse_html()`:

```python
for card in soup.select('div.poly-card--grid-card'):
    product = {
        'product_name': card.find('a', class_='poly-component__title').text.strip(),
        'original_url': link_tag.get('href', '').split('#')[0],  # Remove tracking
        'image_url': image_tag.get('data-src') or image_tag.get('src'),
        'list_price': self._clean_price(list_price_tag.text),  # R$ 1.299,99 → 1299.99
        'sale_price': float(f"{fraction.text},{cents.text}"),  # 899,99 → 899.99
        'installments_info': installments_tag.text.strip(),
        'shipping_info': shipping_tag.text.strip(),
        'is_full': svg.poly-shipping__promise-icon--full is not None
    }
```

### Método `_clean_price()`:

```python
def _clean_price(self, price_str):
    # "R$ 1.299,99" → 1299.99
    cleaned = price_str.replace('R$', '').replace('.', '').replace(',', '.').strip()
    return float(cleaned)
```

---

## 🔗 GERAÇÃO DE LINKS (link_generator.py)

### Processo em Lotes:

```python
# Processa URLs em grupos de LINKS_PER_BATCH
for batch_idx in range(0, len(product_urls), urls_per_batch):
    batch_urls = product_urls[batch_idx:batch_idx + urls_per_batch]
    urls_text = '\n'.join(batch_urls)

    # IMPORTANTE: Usa JavaScript direto para NÃO usar clipboard!
    # (page.fill() do Playwright usa clipboard internamente)
    textarea_element = page.query_selector(textarea_selector)
    page.evaluate('''(args) => {
        const [el, text] = args;
        el.value = text;
        el.dispatchEvent(new Event("input", { bubbles: true }));
    }''', [textarea_element, urls_text])

    # Clica em "Gerar" UMA VEZ para todas
    page.click('button.andes-button--loud')

    # Aguarda proporcional ao número de URLs
    wait_time = base_wait + (len(batch_urls) * 0.3)
    time.sleep(wait_time)

    # Extrai links gerados via API nativa
    result_text = textareas[1].input_value()
    generated_links = result_text.strip().split('\n')
```

**IMPORTANTE:** O scraper NÃO usa clipboard. Usa JavaScript direto:
- `page.evaluate()` para inserir dados (define `el.value` diretamente)
- `element.input_value()` para ler dados

---

## 🚀 COMO EXECUTAR

### Pré-requisitos:
1. Docker rodando com container `n8n_postgres_db`
2. Python 3.10+ com venv configurado
3. Sessão do ML já logada (executar `login_session.py` primeiro)

### Comandos:

```powershell
# Ativar venv
cd C:\Users\guii7\bear_cave_labs\n8n\python_scraper_meli
.\venv\Scripts\Activate.ps1

# Primeira vez: criar sessão de login
python login_session.py

# Executar scraper
python main.py
```

### Via API (n8n):

```
POST http://localhost:5000/api/scrape
Headers: { "Authorization": "Bearer KuuizeHIjN5OSIPvbF6faIb7O4M7zJym924Icrf2kWU" }
```

---

## 📈 RESULTADO TÍPICO

```
======================================================================
MERCADO LIVRE AFFILIATE SCRAPER - v2.0
======================================================================
Iniciado em: 28/11/2025 14:30:00

📦 Inicializando componentes...
✅ Componentes inicializados

======================================================================
ETAPA 1: SCRAPING DE OFERTAS
======================================================================
🔍 Iniciando scraping de 3 URL(s)...
   5 página(s) por URL
   Total esperado: ~15 requisições

📌 URL 1/3: https://www.mercadolivre.com.br/ofertas?promotion_type=lightning...
   ✅ Página 1: 48 produtos
   ✅ Página 2: 48 produtos
   ...

======================================================================
RESUMO DA EXECUÇÃO
======================================================================
Produtos coletados: 240
Links afiliados gerados: 235
Salvos no banco: 180
Pulados (sem link): 5
Falhas: 0
Finalizado em: 28/11/2025 14:35:00
======================================================================
```

---

## 🐛 TROUBLESHOOTING

### Problema: "Navegador não abre"
**Solução:** Verificar se `SESSION_DIR` é caminho absoluto e pasta existe

### Problema: "Links não gerados"
**Solução:**
1. Executar `python login_session.py` para renovar login
2. Verificar se conta ML não está bloqueada

### Problema: "Scraper rouba foco/teclado"
**Solução:** Já corrigido! Usamos flags anti-foco:
- `--disable-focus-stealing-prevention`
- Janela posicionada em -2400,-2400 (fora da tela)
- Usa `input_value()` ao invés de clipboard

### Problema: "Banco não conecta"
**Solução:** Verificar se container Docker está rodando:
```powershell
docker ps | Select-String "postgres"
```

---

## 📝 DEPENDÊNCIAS (requirements.txt)

```txt
playwright==1.51.0
beautifulsoup4==4.12.3
psycopg2-binary==2.9.9
python-dotenv==1.0.1
requests==2.31.0
pyyaml==6.0.2
nest_asyncio==1.6.0
```

---

## 📌 BACKUPS DISPONÍVEIS

- `link_generator_backup_20251128.py` - Versão anterior do gerador de links
- `scraper_backup_20251128.py` - Versão anterior do scraper

---

## ✅ MELHORIAS IMPLEMENTADAS (28/11/2025)

1. **Anti-Foco:** Adicionadas flags do Chrome para não roubar foco do usuário
2. **Sem Clipboard:** Usa `input_value()` do Playwright (API nativa) ao invés de evaluate()
3. **Janela Oculta:** Posiciona navegador em -2400,-2400 quando `BROWSER_WINDOW_HIDDEN=True`
4. **Lotes Otimizados:** Processa 30 URLs por vez no LinkBuilder (muito mais rápido)

---

*Documento gerado automaticamente para compartilhamento de contexto entre IAs*
