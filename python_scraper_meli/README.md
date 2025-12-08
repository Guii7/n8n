# 🎯 Mercado Livre Affiliate Scraper# Mercado Livre Affiliate Scraper (Windows)



**Versão 2.0 - Sistema completo de scraping, geração de links afiliados e persistência em banco de dados**Sistema Python para scraping de ofertas do Mercado Livre, geração de links afiliados e salvamento no banco PostgreSQL do n8n.



> Sistema automatizado para extrair produtos do Mercado Livre, gerar links afiliados em lote e salvar no PostgreSQL com notificações via Telegram.## 🎯 Arquitetura (Opção C)



---```

┌─────────────────────────────────────────────────┐

## 📋 Visão Geral│  Python Script (Windows)                        │

│  ├── 1. Scraping (Playwright)                   │

### O que faz?│  ├── 2. Login + Geração Links (Sessão Windows)  │

│  └── 3. Salvar no PostgreSQL                    │

1. **🔍 Web Scraping**: Coleta produtos do Mercado Livre via Playwright└─────────────────────────────────────────────────┘

2. **🔗 Link Generation**: Converte URLs em links afiliados via Mercado Livre LinkBuilder                      ↓

3. 💾 **Database**: Salva produtos e links no PostgreSQL┌─────────────────────────────────────────────────┐

4. 📱 **Notifications**: Envia resultado via Telegram (sucesso ou erro)│  n8n Workflow (Docker)                          │

│  ├── 1. Query Database (novas ofertas)          │

### Principais características│  ├── 2. Formatar mensagens                      │

│  └── 3. Enviar para Telegram/Discord            │

- ✅ **Sessão Persistente**: Reutiliza login do Windows (não precisa fazer login toda execução)└─────────────────────────────────────────────────┘

- ✅ **Batch Processing**: Gera múltiplos links simultâneos (5-10x mais rápido)```

- ✅ **Background Mode**: Roda sem interferir no seu Ctrl+C/Ctrl+V

- ✅ **Configurável**: Tudo controlável via `.env`**Por que essa abordagem funciona:**

- ✅ **Robusto**: Tratamento de erros e retry automático- ✅ Usa sessão persistente do Windows (cookies compatíveis)

- ✅ **Performance**: ~20-30 minutos para 800+ produtos- ✅ Login manual uma vez, reutiliza sessão

- ✅ Playwright mais robusto que Puppeteer

---- ✅ n8n só precisa fazer queries e enviar mensagens



## 🚀 Quick Start## 📦 Arquivos



### 1. Pré-requisitos- `scraper.py` - Coleta ofertas do Mercado Livre

- `link_generator.py` - Gera links afiliados usando sessão Windows

```- `db_manager.py` - Gerencia conexão com PostgreSQL

✓ Python 3.10+- `main.py` - Orquestra todo o processo

✓ PostgreSQL rodando- `requirements.txt` - Dependências Python

✓ Docker (n8n com PostgreSQL integrado)- `.env.example` - Template de variáveis de ambiente

✓ Chrome/Chromium instalado

✓ Conta Mercado Livre com acesso ao programa de afiliados## 🚀 Setup

✓ Bot Telegram criado (opcional, para notificações)

```### 1. Instalar Python 3.10+



### 2. InstalaçãoVerifique se Python está instalado:

```cmd

```bashpython --version

# Clone ou extraia o projeto```

cd python_scraper_meli

Se não estiver: https://www.python.org/downloads/

# Crie ambiente virtual

python -m venv venv### 2. Criar Ambiente Virtual



# Ative o ambiente (Windows)```cmd

venv\Scripts\activatecd C:\Users\guii7\n8n\n8n\python_scraper_meli

python -m venv venv

# Instale dependências```

pip install -r requirements.txt

```### 3. Ativar Ambiente Virtual



### 3. Configuração```cmd

venv\Scripts\activate

Copie `.env.example` para `.env` e preencha:```



```bash### 4. Instalar Dependências

# Credenciais Mercado Livre

ML_EMAIL=seu_email@gmail.com```cmd

ML_PASSWORD=sua_senhapip install -r requirements.txt

```

# PostgreSQL (Docker n8n)

POSTGRES_HOST=localhost### 5. Instalar Playwright Browsers

POSTGRES_PORT=5432

POSTGRES_DB=n8n```cmd

POSTGRES_USER=n8n_userplaywright install chromium

POSTGRES_PASSWORD=sua_senha```



# URLs para scraping### 6. Configurar Variáveis de Ambiente

SCRAPING_URLS=url1,url2,url3

Copie `.env.example` para `.env`:

# Telegram (opcional)```cmd

TELEGRAM_CHAT_ID=seu_chat_idcopy .env.example .env

TELEGRAM_BOT_TOKEN_SUCCESS=token```

TELEGRAM_BOT_TOKEN_ERROR=token

```Edite `.env` e configure:

- `ML_EMAIL` - Seu email do Mercado Livre

### 4. Primeira execução- `ML_PASSWORD` - Sua senha

- `POSTGRES_*` - Dados de conexão do PostgreSQL (já estão corretos)

```bash- `HEADLESS` - `False` para ver navegador, `True` para rodar em background

# Executar manualmente (fará login via QR code na primeira vez)- `MAX_PAGES` - Quantas páginas de ofertas buscar (1-10)

python main.py- `SESSION_DIR` - Pasta da sessão do Chrome (já configurado)

```

## 🔐 Primeiro Login

Se tudo funcionou:

- ✅ ~30-40 produtos coletados por URLAntes de rodar automatizado, faça login manual uma vez:

- ✅ ~80% dos produtos com links gerados

- ✅ Dados salvos no PostgreSQL```cmd

- ✅ Telegram recebe notificação de sucessopython link_generator.py

- ✅ Exit code: 0```



---Isso vai:

1. Abrir Chrome

## 📁 Estrutura de Arquivos2. Pedir para você fazer login

3. Aguardar 2FA

```4. Salvar sessão para reuso

python_scraper_meli/

├── main.py                 # 🔴 PONTO DE ENTRADA - Orquestra tudo**Importante:** Use o mesmo diretório de sessão que usou nos scripts manuais (`C:\Users\guii7\n8n\puppeteer_session`).

├── scraper.py              # Web scraping com Playwright

├── link_generator.py       # Geração de links afiliados## ▶️ Execução Manual

├── db_manager.py           # Gerenciamento PostgreSQL

├── telegram_notifier.py    # Notificações Telegram### Testar Scraper

│

├── .env                    # ⚙️ CONFIGURAÇÃO PRINCIPAL```cmd

├── .env.example            # Templatepython scraper.py

├── config.yml              # Configuração adicional (se needed)```

├── requirements.txt        # Dependências Python

│### Testar Gerador de Links

├── CONFIGURATION.md        # 📖 Como configurar variáveis .env

├── CLIPBOARD_SOLUTION.md   # 📖 Solução para não bloquear Ctrl+C/Ctrl+V```cmd

├── README.md               # 📖 Este arquivopython link_generator.py

│```

├── venv/                   # Ambiente virtual

├── logs/                   # Pasta de logs### Testar Banco de Dados

└── puppeteer_session/      # Sessão do Chromium (autologin)

``````cmd

python db_manager.py

---```



## ⚙️ Configuração Detalhada### Executar Completo



### Arquivo `.env````cmd

python main.py

#### 🔐 Credenciais Mercado Livre```



```env## ⏰ Agendamento Automático (Windows Task Scheduler)

ML_EMAIL=seu_email@gmail.com

ML_PASSWORD=sua_senha### Criar Tarefa Agendada

```

1. Abra **Agendador de Tarefas**

#### 🗄️ PostgreSQL2. **Criar Tarefa Básica**

3. Nome: `Mercado Livre Scraper`

```env4. Gatilho: **Diariamente** às **08:00** e **20:00**

POSTGRES_HOST=localhost5. Ação: **Iniciar um programa**

POSTGRES_PORT=5432

POSTGRES_DB=n8n```

POSTGRES_USER=n8n_userPrograma/script: C:\Users\guii7\n8n\n8n\python_scraper_meli\venv\Scripts\python.exe

POSTGRES_PASSWORD=sua_senhaArgumentos: C:\Users\guii7\n8n\n8n\python_scraper_meli\main.py

```Iniciar em: C:\Users\guii7\n8n\n8n\python_scraper_meli

```

#### 🖥️ Configurações do Navegador

### Ou usar PowerShell Script

```env

HEADLESS=False                    # Não usar headless (ML bloqueia)Crie `run_scraper.ps1`:

BROWSER_WINDOW_HIDDEN=True        # ✅ Janela oculta (não bloqueia input)```powershell

MAX_PAGES=5                       # Páginas por URLcd C:\Users\guii7\n8n\n8n\python_scraper_meli

SESSION_DIR=C:\Users\...\puppeteer_session  # Caminho absoluto.\venv\Scripts\Activate.ps1

```python main.py

```

#### 🔗 Link Generation

Agende para rodar 2x ao dia.

```env

LINKS_PER_BATCH=8                 # Links por requisição (8-10 ideal)## 🔄 Workflow n8n Simplificado

LINK_GENERATION_WAIT_TIME=2       # Segundos base para gerar

```O n8n agora só precisa:



#### 🌐 URLs de Scraping1. **Trigger** - Schedule (a cada 1 hora)

2. **Query** - PostgreSQL:

```env   ```sql

SCRAPING_URLS=url1,url2,url3   SELECT * FROM mercado_livre_offers

# NÃO incluir ?page= ou &page= (adicionado automaticamente)   WHERE status = 'new'

```   AND created_at > NOW() - INTERVAL '1 hours'

   ORDER BY sale_price ASC

#### 📱 Telegram (Opcional)   LIMIT 20

   ```

```env3. **Format** - Código JS para formatar mensagem

TELEGRAM_CHAT_ID=seu_id4. **Send** - Telegram/Discord

TELEGRAM_BOT_TOKEN_SUCCESS=token5. **Update** - Marcar como `sent`:

TELEGRAM_BOT_TOKEN_ERROR=token   ```sql

API_URL=http://localhost:5000   UPDATE mercado_livre_offers

```   SET status = 'sent'

   WHERE id = {{$json.id}}

### 📖 Para mais detalhes   ```



→ Veja `CONFIGURATION.md` para guia completo de variáveis  ## 📊 Tabela PostgreSQL

→ Veja `CLIPBOARD_SOLUTION.md` para solução de input bloqueado

A tabela `mercado_livre_offers` já existe no banco do n8n:

---

```sql

## 🎮 Como UsarCREATE TABLE IF NOT EXISTS mercado_livre_offers (

    id SERIAL PRIMARY KEY,

### Execução Manual    product_name TEXT NOT NULL,

    original_url TEXT UNIQUE NOT NULL,

```bash    affiliate_url TEXT,

# Ativar ambiente    image_url TEXT,

venv\Scripts\activate    list_price DECIMAL(10,2),

    sale_price DECIMAL(10,2),

# Executar    installments_info TEXT,

python main.py    shipping_info TEXT,

```    is_full BOOLEAN DEFAULT FALSE,

    status VARCHAR(20) DEFAULT 'new',

**Tempo esperado**: 20-30 minutos para 800+ produtos    created_at TIMESTAMP DEFAULT NOW(),

    updated_at TIMESTAMP DEFAULT NOW()

**Logs esperados:**);

``````

✅ Componentes inicializados

📊 Scraping iniciado## 🐛 Troubleshooting

🌐 Página 1: 40 produtos encontrados

🔗 Gerando links (8 por lote)...### Erro: "Não foi possível resolver a importação"

💾 Salvando no banco...```cmd

✅ 801 produtos coletadospip install -r requirements.txt

✅ 641 links gerados (80%)playwright install chromium

✅ 720 salvos no banco```

Exit code: 0 ✅

```### Erro: "Connection refused" ao conectar PostgreSQL

Verifique se Docker está rodando:

### Agendamento Automático (Task Scheduler do Windows)```cmd

docker ps | findstr postgres

Ver documentação separada para configurar no Windows Task Scheduler.```



**Recomendações:**### Erro: "Sessão inválida" ao gerar links

- Executar 1-2x por diaExecute login manual novamente:

- Hora: fora de pico (madrugada ou final do expediente)```cmd

- Notificações: Telegram informará sucesso/erropython link_generator.py

```

---

### Chrome não abre

## 🔍 Logs e DebugInstale browsers do Playwright:

```cmd

### Onde estão os logs?playwright install --with-deps chromium

```

```

python_scraper_meli/logs/  # Arquivos de log por execução## 📝 Logs

```

Todos os prints vão para `stdout`. Para salvar em arquivo:

### Entender os status codes

```cmd

```python main.py >> logs.txt 2>&1

Exit Code 0 → ✅ Sucesso completo```

Exit Code 1 → ❌ Erro (Telegram será notificado)

```## 🔒 Segurança



### Telegram recebe:- ⚠️ **NÃO comite o arquivo `.env`**

- ⚠️ Adicione `.env` ao `.gitignore`

**Sucesso:**- ⚠️ Credenciais são armazenadas localmente

```- ✅ Sessão do Chrome já persiste em `puppeteer_session/`

✅ Scraper Mercado Livre

801 produtos coletados## 📈 Próximos Passos

641 links gerados (80%)

720 salvos em DB1. ✅ Criar estrutura Python

Tempo: 27min 45seg2. ✅ Implementar scraper

```3. ✅ Implementar gerador de links

4. ✅ Integrar com PostgreSQL

**Erro:**5. ⏳ **Testar execução completa** ← Você está aqui

```6. ⏳ Simplificar workflow n8n

❌ Erro no Scraper7. ⏳ Agendar execução automática

Detalhes: [mensagem de erro]8. ⏳ Monitorar e ajustar

Verificar logs em python_scraper_meli/logs/

```## 💡 Dicas



---- Comece com `MAX_PAGES=1` para testar

- Use `HEADLESS=False` durante desenvolvimento

## 🔧 Troubleshooting- Verifique cookies em `SESSION_DIR\Default\Network\Cookies`

- PostgreSQL exposto em `localhost:5433` (não 5432)

### "Conexão recusada ao PostgreSQL"

## 📞 Suporte

```bash

# Verificar se Docker está rodandoSe encontrar problemas:

docker ps1. Verifique Docker: `docker ps`

2. Verifique Python: `python --version`

# Se não está, inicie3. Verifique PostgreSQL: `python db_manager.py`

docker-compose up -d4. Execute testes individuais antes do `main.py`

```

### "Sync API inside asyncio loop"

Geralmente já foi tratado. Se persistir:

```bash
# Deletar sessão do navegador
rm -rf puppeteer_session

# Executar novamente
python main.py
```

### "Nenhum link afiliado gerado"

```
Verificar:
1. Conta está vinculada ao programa de afiliados? (ML)
2. HEADLESS está False? (True bloqueia)
3. Aumentar LINK_GENERATION_WAIT_TIME para 3-4s
```

### "Script bloqueia Ctrl+C/Ctrl+V"

✅ **Já resolvido!** Configure no `.env`:

```env
BROWSER_WINDOW_HIDDEN=True    # ← Ativa solução
```

Ver `CLIPBOARD_SOLUTION.md` para detalhes.

### "Timeout ou execução muito lenta"

```env
# Reduzir volume:
LINKS_PER_BATCH=5             # Reduzir de 8 para 5
LINK_GENERATION_WAIT_TIME=3   # Aumentar de 2 para 3
MAX_PAGES=3                   # Reduzir de 5 para 3
```

---

## 📊 Estrutura do Banco de Dados

### Tabela `products` (criada automaticamente)

```sql
id              INTEGER PRIMARY KEY
product_id      TEXT
title           TEXT
price           DECIMAL
url             TEXT
affiliate_link  TEXT
status          VARCHAR (pending/completed/failed)
collected_at    TIMESTAMP
generated_at    TIMESTAMP
saved_at        TIMESTAMP
```

A tabela é criada automaticamente na primeira execução.

---

## 🔄 Fluxo de Execução

```
1. INICIALIZAR
   └─ Validar .env e banco de dados

2. SCRAPING
   └─ Para cada URL em SCRAPING_URLS:
      ├─ MAX_PAGES páginas
      └─ Extrair ~40 produtos por página

3. LINK GENERATION
   └─ Agrupar produtos em lotes (LINKS_PER_BATCH)
      ├─ Enviar N URLs ao LinkBuilder
      ├─ Aguardar resposta
      └─ Extrair N links

4. DATABASE
   └─ Salvar produtos + links no PostgreSQL

5. NOTIFICAÇÃO
   └─ Enviar resultado via Telegram

6. EXIT
   └─ Code 0 (sucesso) ou 1 (erro)
```

---

## ⚡ Performance

### Benchmarks (com config padrão)

| Fase | Tempo | Produtos |
|------|-------|----------|
| Scraping | 15-20 min | 800+ |
| Link Gen | 5-10 min | 80% sucesso |
| Database | 1-2 min | 720+ |
| **Total** | **~27 min** | **800 → 720** |

### Como Melhorar Performance

**Se está lento:**

```env
LINKS_PER_BATCH=10        # Aumentar de 8
LINK_GENERATION_WAIT_TIME=1.5  # Reduzir de 2
MAX_PAGES=10              # Aumentar de 5
```

**⚠️ Trade-off:** Maior risco de timeout ou bloqueio

**Recomendado:**
- LINKS_PER_BATCH: 8-10
- LINK_GENERATION_WAIT_TIME: 2-2.5
- MAX_PAGES: 5-7

---

## 🆘 Suporte e Debugging

### Informações Técnicas

**Stack:**
- Python 3.10+
- Playwright (Chromium)
- BeautifulSoup4 (parsing HTML)
- PostgreSQL (banco de dados)
- Telegram Bot API

**Dependências principais** (veja `requirements.txt`):

```
playwright>=1.40
beautifulsoup4>=4.12
psycopg2-binary>=2.9
python-dotenv>=1.0
requests>=2.31 (Telegram)
nest-asyncio>=1.5 (asyncio fix)
```

### Checklist de Diagnóstico

Antes de reportar um erro:

```
□ Variáveis .env estão preenchidas? (ML_EMAIL, ML_PASSWORD, POSTGRES_*)
□ Docker rodando? (docker ps mostra containers)
□ Conta ML vinculada ao programa de afiliados?
□ Chrome/Chromium instalado?
□ Python 3.10+? (python --version)
□ Virtual env ativado? (venv\Scripts\activate)
□ Dependências instaladas? (pip install -r requirements.txt)
□ HEADLESS=False no .env?
□ BROWSER_WINDOW_HIDDEN=True no .env?
```

---

## 📚 Documentação Adicional

| Documento | Assunto |
|-----------|---------|
| `CONFIGURATION.md` | Guia completo de variáveis .env |
| `CLIPBOARD_SOLUTION.md` | Solução para não bloquear input |

---

## 📝 Versão e Changelog

### v2.0 (Atual)

✅ **Principais melhorias:**

- ✨ Link generation em lote (5-6x mais rápido)
- 🪟 Browser em background (não bloqueia input)
- ⚙️ Configurável via `.env` (sem editar código)
- 📱 Notificações Telegram
- 🗄️ Persistência em PostgreSQL
- 🔄 Retry automático
- 🎯 Exit codes corretos (0 = sucesso, 1 = erro)
- 🛡️ Tratamento robusto de erros

### Histórico

v1.0 → Primeira versão (link 1-por-1, lento)
v1.5 → Sessão persistente
v2.0 → Link batch + background + configurable

---

## ✅ Checklist de Produção

Antes de colocar em produção:

```
□ .env preenchido com todas as variáveis
□ PostgreSQL rodando e acessível
□ Bot Telegram criado e testado
□ Conta ML vinculada ao programa de afiliados
□ URLs de scraping validadas (sem ?page=)
□ Primeira execução manual realizada com sucesso
□ Task Scheduler criado para execução automática
□ Logs sendo gerados em python_scraper_meli/logs/
□ Telegram recebendo notificações corretamente
```

---

## 🔐 Segurança

### ⚠️ IMPORTANTE

```
NUNCA versione o .env em git!
Ele contém credenciais sensíveis.

Use .env.example como template
Adicione .env ao .gitignore (já está)
```

### Senhas e Tokens

- **ML_PASSWORD**: Encrypt em produção (considere gestão de secrets)
- **TELEGRAM_BOT_TOKEN**: Nunca compartilhe publicamente
- **POSTGRES_PASSWORD**: Use senha forte

---

## 📞 Contato e Suporte

Para problemas:

1. Verificar `CONFIGURATION.md` e `CLIPBOARD_SOLUTION.md`
2. Revisar checklist de diagnóstico (veja seção anterior)
3. Verificar logs em `python_scraper_meli/logs/`
4. Consultar seção **Troubleshooting** acima

---

## 🎉 Conclusão

Sistema **pronto para produção**, otimizado e fácil de manter.

**Últimas execuções confirmaram:**
- ✅ 800+ produtos coletados
- ✅ 80% de links gerados com sucesso
- ✅ Salvo no banco de dados
- ✅ Notificações via Telegram funcionando
- ✅ Exit code 0 em sucesso
- ✅ Não bloqueia input do sistema

**Use, configure conforme necessário, e agende para rodar automaticamente!** 🚀

---

**Última atualização:** 22 de outubro de 2025
**Versão:** 2.0
**Status:** ✅ Pronto para Produção
