"""
Telegram Notifier - Envia resultados de execução para Telegram
Versão 2.0 - 2 Bots diferentes: Um para sucesso, outro para erro
Notificações formatadas com emoji e métricas
"""
import os
import logging
import requests
from dotenv import load_dotenv
from datetime import datetime
from zoneinfo import ZoneInfo

load_dotenv()

logger = logging.getLogger(__name__)

# Timezone de Brasília
BRAZIL_TZ = ZoneInfo('America/Sao_Paulo')


class TelegramNotifier:
    """Envia notificações para Telegram usando Bot API (2 bots: sucesso e erro)"""

    def __init__(self):
        """Inicializa credenciais de 2 bots do Telegram"""
        # Chat ID (único para ambos os bots)
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')

        # Bot de SUCESSO (quando tudo der certo)
        self.bot_token_success = os.getenv('TELEGRAM_BOT_TOKEN_SUCCESS')

        # Bot de ERRO (quando houver problemas)
        self.bot_token_error = os.getenv('TELEGRAM_BOT_TOKEN_ERROR')

        # Verifica quais bots estão configurados
        self.success_enabled = bool(self.bot_token_success and self.chat_id)
        self.error_enabled = bool(self.bot_token_error and self.chat_id)

        if not self.success_enabled and not self.error_enabled:
            logger.warning("⚠️ Telegram não configurado (faltam tokens dos bots)")
        else:
            if self.success_enabled:
                logger.info("✅ Bot de SUCESSO configurado")
            if self.error_enabled:
                logger.info("✅ Bot de ERRO configurado")

    def send_execution_result(self, execution_data):
        """
        Envia resultado de execução para Telegram (bot de sucesso OU erro)

        Args:
            execution_data (dict): Dados da execução com chaves:
                - products_scraped: int (quantidade de produtos coletados)
                - links_generated: int (quantidade de links gerados)
                - links_saved: int (quantidade de links salvos no banco)
                - execution_time: float (tempo em segundos)
                - success: bool (se a execução foi bem-sucedida)
                - error_message: str (mensagem de erro, se houver)
                - job_id: str (identificador do job)

        Returns:
            bool: True se enviado com sucesso, False caso contrário
        """
        success = execution_data.get('success', False)

        if success:
            if not self.success_enabled:
                logger.debug("Bot de SUCESSO desabilitado")
                return False
            return self._send_success_message(execution_data)
        else:
            if not self.error_enabled:
                logger.debug("Bot de ERRO desabilitado")
                return False
            return self._send_error_message(execution_data)

    def _send_success_message(self, execution_data):
        """Envia mensagem de SUCESSO"""
        try:
            message = self._format_success_message(execution_data)
            return self._send_telegram_message(message, self.bot_token_success)
        except Exception as e:
            logger.error(f"❌ Erro ao enviar mensagem de sucesso: {e}", exc_info=True)
            return False

    def _send_error_message(self, execution_data):
        """Envia mensagem de ERRO"""
        try:
            message = self._format_error_message(execution_data)
            return self._send_telegram_message(message, self.bot_token_error)
        except Exception as e:
            logger.error(f"❌ Erro ao enviar mensagem de erro: {e}", exc_info=True)
            return False

    def _send_telegram_message(self, message, bot_token):
        """Envia mensagem via Telegram Bot API"""
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML"
            }

            response = requests.post(url, json=payload, timeout=10)

            if response.status_code == 200:
                logger.info("✅ Notificação enviada para Telegram com sucesso")
                return True
            else:
                logger.error(f"❌ Erro ao enviar para Telegram: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"❌ Erro ao enviar notificação Telegram: {e}", exc_info=True)
            return False

    def _format_success_message(self, data):
        """Formata mensagem de SUCESSO para Telegram com emojis e HTML"""
        timestamp = datetime.now(BRAZIL_TZ).strftime('%d/%m/%Y, %H:%M:%S')

        lines = [
            "📊 <b>Relatório de Scraping - Mercado Livre</b>",
            "",
            f"🕐 <b>Hora:</b> {timestamp}",
            f"📦 <b>Total Processado:</b> {data.get('products_scraped', 0)}",
            f"🆕 <b>Novos/Atualizados:</b> {data.get('links_saved', 0)}",
            f"♻️  <b>Sem Alteração:</b> {data.get('products_scraped', 0) - data.get('links_saved', 0)}",
            "",
            "✅ <b>Scraping concluído com sucesso!</b>",
        ]

        # Adicionar mais detalhes se disponível
        if data.get('links_generated'):
            lines.insert(5, f"🔗 <b>Links Gerados:</b> {data['links_generated']}")

        if data.get('execution_time'):
            lines.append(f"⏱️  <b>Tempo:</b> {data['execution_time']:.2f}s")

        return "\n".join(lines)

    def _format_error_message(self, data):
        """Formata mensagem de ERRO para Telegram com emojis e HTML"""
        timestamp = datetime.now(BRAZIL_TZ).strftime('%d/%m, %H:%M')
        job_id = data.get('job_id', 'unknown')

        lines = [
            "❌ <b>ERRO - Meli Scraper Falhou</b>",
            "",
            f"🔴 <b>Status:</b> failed",
            f"📦 <b>Job ID:</b> {job_id}",
            f"⏰ <b>Hora:</b> {timestamp}",
            "",
            f"💬 <b>Erro:</b>",
        ]

        # Adicionar mensagem de erro (truncar se muito longa)
        error_msg = data.get('error_message') or 'Erro desconhecido'
        if error_msg and len(str(error_msg)) > 500:
            lines.append(f"<code>{str(error_msg)[:500]}...</code>")
        else:
            lines.append(f"<code>{str(error_msg)}</code>")

        # Adicionar referência aos logs
        lines.extend([
            "",
            "🔧 <b>Verifique os logs da API para detalhes completos</b>",
        ])

        return "\n".join(lines)

    def send_startup_notification(self):
        """Envia notificação de inicialização (apenas se bot de sucesso configurado)"""
        if not self.success_enabled:
            return False

        try:
            timestamp = datetime.now(BRAZIL_TZ).strftime('%d/%m/%Y %H:%M:%S')
            message = f"🚀 <b>Scraper iniciado</b>\n⏰ {timestamp}"
            return self._send_telegram_message(message, self.bot_token_success)
        except Exception as e:
            logger.error(f"Erro ao enviar notificação de inicialização: {e}")
            return False

    def send_custom_error(self, error_message, job_id=None):
        """Envia notificação de erro customizada"""
        if not self.error_enabled:
            return False

        data = {
            'success': False,
            'error_message': error_message,
            'job_id': job_id or 'manual'
        }
        return self._send_error_message(data)


# Singleton para uso global
_notifier_instance = None


def get_notifier():
    """Retorna instância global do TelegramNotifier"""
    global _notifier_instance
    if _notifier_instance is None:
        _notifier_instance = TelegramNotifier()
    return _notifier_instance


def send_execution_result(execution_data):
    """Atalho para enviar resultado de execução"""
    return get_notifier().send_execution_result(execution_data)


def send_error(error_message, job_id=None):
    """Atalho para enviar erro customizado"""
    return get_notifier().send_custom_error(error_message, job_id)
