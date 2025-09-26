"""
Notification Service Module
Модуль для управління чергою сповіщень та надійної доставки повідомлень
"""

import json
import logging
import smtplib
import threading
import time
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any, Optional
from sqlalchemy import and_

from models import db, User, NotificationQueue, NotificationSettings, NotificationStatus
from telegram_service import TelegramService

# Налаштування логера з детальним форматуванням
logger = logging.getLogger(__name__)

class NotificationMetrics:
    """Клас для збору метрик системи сповіщень"""
    
    def __init__(self):
        self.reset_metrics()
    
    def reset_metrics(self):
        """Скинути метрики"""
        self.total_sent = 0
        self.total_failed = 0
        self.telegram_sent = 0
        self.telegram_failed = 0
        self.email_sent = 0
        self.email_failed = 0
        self.processing_times = []
        self.error_counts = {}
    
    def record_success(self, notification_type: str, processing_time: float = None):
        """Записати успішну відправку"""
        self.total_sent += 1
        if notification_type == 'telegram':
            self.telegram_sent += 1
        elif notification_type == 'email':
            self.email_sent += 1
        
        if processing_time:
            self.processing_times.append(processing_time)
    
    def record_failure(self, notification_type: str, error_type: str):
        """Записати невдалу відправку"""
        self.total_failed += 1
        if notification_type == 'telegram':
            self.telegram_failed += 1
        elif notification_type == 'email':
            self.email_failed += 1
        
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
    
    def get_success_rate(self) -> float:
        """Отримати відсоток успішності"""
        total = self.total_sent + self.total_failed
        return (self.total_sent / total * 100) if total > 0 else 0
    
    def get_average_processing_time(self) -> float:
        """Отримати середній час обробки"""
        return sum(self.processing_times) / len(self.processing_times) if self.processing_times else 0

class NotificationService:
    """Сервіс для управління сповіщеннями"""
    
    def __init__(self, app=None):
        self.app = app
        self.smtp_server = None
        self.smtp_port = None
        self.smtp_username = None
        self.smtp_password = None
        self.from_email = None
        self._running = False
        self._worker_thread = None
        self.queue_check_interval = 30  # секунд
        self.metrics = NotificationMetrics()
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Ініціалізація з Flask додатком"""
        self.app = app
        self.smtp_server = app.config.get('SMTP_SERVER')
        self.smtp_port = app.config.get('SMTP_PORT', 587)
        self.smtp_username = app.config.get('SMTP_USERNAME')
        self.smtp_password = app.config.get('SMTP_PASSWORD')
        self.from_email = app.config.get('FROM_EMAIL')
        self.queue_check_interval = app.config.get('NOTIFICATION_QUEUE_CHECK_INTERVAL', 30)
        
        logger.info("NotificationService initialized", extra={
            'smtp_configured': bool(self.smtp_server and self.smtp_username),
            'queue_interval': self.queue_check_interval
        })

    def add_notification(self, user_id: int, notification_type: str, message_content: str, 
                        survey_id: Optional[int] = None, metadata: Optional[Dict] = None) -> bool:
        """
        Додати сповіщення до черги
        
        Args:
            user_id: ID користувача
            notification_type: Тип сповіщення ('telegram' або 'email')
            message_content: Зміст повідомлення
            survey_id: ID опитування (опціонально)
            metadata: Додаткові дані (опціонально)
            
        Returns:
            True якщо успішно додано
        """
        start_time = time.time()
        
        try:
            logger.debug("Adding notification", extra={
                'user_id': user_id,
                'notification_type': notification_type,
                'survey_id': survey_id,
                'has_metadata': bool(metadata)
            })
            
            notification = NotificationQueue(
                user_id=user_id,
                notification_type=notification_type,
                message_content=message_content,
                survey_id=survey_id,
                status=NotificationStatus.PENDING.value,
                scheduled_at=datetime.utcnow(),
                created_at=datetime.utcnow()
            )
            
            if metadata:
                notification.set_metadata(metadata)
            
            db.session.add(notification)
            db.session.commit()
            
            processing_time = time.time() - start_time
            logger.info("Notification added successfully", extra={
                'notification_id': notification.id,
                'user_id': user_id,
                'notification_type': notification_type,
                'processing_time': processing_time
            })
            
            return True
            
        except Exception as e:
            db.session.rollback()
            processing_time = time.time() - start_time
            logger.error("Failed to add notification", extra={
                'user_id': user_id,
                'notification_type': notification_type,
                'error': str(e),
                'processing_time': processing_time
            }, exc_info=True)
            return False
    
    def add_survey_notifications(self, user: User, survey_id: int, message_content: str) -> Dict[str, bool]:
        """
        Додати сповіщення для всіх налаштованих каналів користувача
        
        Args:
            user: Користувач
            survey_id: ID опитування
            message_content: Зміст повідомлення
            
        Returns:
            Словник з результатами для кожного типу сповіщення
        """
        results = {}
        
        # Telegram сповіщення
        if user.has_valid_telegram_settings():
            results['telegram'] = self.add_notification(
                user_id=user.id,
                notification_type='telegram',
                message_content=message_content,
                survey_id=survey_id,
                metadata={
                    'chat_id': user.telegram_group_id,
                    'bot_token': user.bot_token
                }
            )
        
        # Email сповіщення
        if user.has_valid_email_settings():
            results['email'] = self.add_notification(
                user_id=user.id,
                notification_type='email',
                message_content=message_content,
                survey_id=survey_id,
                metadata={
                    'email_address': user.email_address,
                    'restaurant_name': user.restaurant_name
                }
            )
        
        return results
    
    def process_pending_notifications(self) -> Dict[str, int]:
        """
        Обробити всі очікуючі сповіщення
        
        Returns:
            Статистика обробки
        """
        start_time = time.time()
        
        try:
            logger.debug("Starting notification processing")
            
            # Отримуємо сповіщення готові для обробки
            notifications = NotificationQueue.query.filter(
                and_(
                    NotificationQueue.status.in_([
                        NotificationStatus.PENDING.value,
                        NotificationStatus.RETRYING.value
                    ]),
                    NotificationQueue.scheduled_at <= datetime.utcnow()
                )
            ).limit(50).all()  # Обмежуємо кількість для уникнення перевантаження
            
            stats = {
                'processed': 0,
                'sent': 0,
                'failed': 0,
                'retried': 0
            }
            
            for notification in notifications:
                try:
                    notification_start_time = time.time()
                    
                    logger.debug("Processing notification", extra={
                        'notification_id': notification.id,
                        'user_id': notification.user_id,
                        'type': notification.notification_type,
                        'attempt': notification.retry_count + 1
                    })
                    
                    success = self._send_notification(notification)
                    notification_processing_time = time.time() - notification_start_time
                    
                    if success:
                        notification.status = NotificationStatus.SENT.value
                        notification.sent_at = datetime.utcnow()
                        stats['sent'] += 1
                        self.metrics.record_success(notification.notification_type, notification_processing_time)
                        
                        logger.info("Notification sent successfully", extra={
                            'notification_id': notification.id,
                            'user_id': notification.user_id,
                            'type': notification.notification_type,
                            'processing_time': notification_processing_time
                        })
                    else:
                        # Логіка повторних спроб
                        notification.retry_count += 1
                        if notification.retry_count >= 3:
                            notification.status = NotificationStatus.FAILED.value
                            stats['failed'] += 1
                            self.metrics.record_failure(notification.notification_type, 'max_retries_exceeded')
                            
                            logger.error("Notification failed permanently", extra={
                                'notification_id': notification.id,
                                'user_id': notification.user_id,
                                'type': notification.notification_type,
                                'retry_count': notification.retry_count,
                                'error_message': notification.error_message
                            })
                        else:
                            notification.status = NotificationStatus.RETRYING.value
                            # Експоненційна затримка: 5, 15, 45 хвилин
                            delay_minutes = 5 * (3 ** (notification.retry_count - 1))
                            notification.scheduled_at = datetime.utcnow() + timedelta(minutes=delay_minutes)
                            stats['retried'] += 1
                            self.metrics.record_failure(notification.notification_type, 'retry_scheduled')
                            
                            logger.warning("Notification retry scheduled", extra={
                                'notification_id': notification.id,
                                'user_id': notification.user_id,
                                'type': notification.notification_type,
                                'retry_count': notification.retry_count,
                                'next_attempt': notification.scheduled_at.isoformat(),
                                'delay_minutes': delay_minutes
                            })
                    
                    stats['processed'] += 1
                    
                except Exception as e:
                    logger.error("Error processing individual notification", extra={
                        'notification_id': notification.id,
                        'user_id': notification.user_id,
                        'error': str(e)
                    }, exc_info=True)
                    continue
            
            db.session.commit()
            
            total_processing_time = time.time() - start_time
            logger.info("Notification processing completed", extra={
                'stats': stats,
                'total_processing_time': total_processing_time,
                'notifications_per_second': stats['processed'] / total_processing_time if total_processing_time > 0 else 0
            })
            
            return stats
            
        except Exception as e:
            db.session.rollback()
            total_processing_time = time.time() - start_time
            logger.critical("Critical error in notification processing", extra={
                'error': str(e),
                'processing_time': total_processing_time
            }, exc_info=True)
            
            # Тригер алерту для критичних помилок
            self._trigger_critical_alert("notification_processing_failed", str(e))
            
            return {
                'processed': 0,
                'sent': 0,
                'failed': 0,
                'retried': 0
            }
    
    def _send_notification(self, notification: NotificationQueue) -> bool:
        """
        Відправити конкретне сповіщення
        
        Args:
            notification: Сповіщення для відправки
            
        Returns:
            True якщо успішно відправлено
        """
        try:
            if notification.notification_type == 'telegram':
                return self._send_telegram_notification(notification)
            elif notification.notification_type == 'email':
                return self._send_email_notification(notification)
            else:
                logger.error(f"Unknown notification type: {notification.notification_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending {notification.notification_type} notification: {e}")
            return False
    
    def _send_telegram_notification(self, notification: NotificationQueue) -> bool:
        """
        Відправити Telegram сповіщення
        
        Args:
            notification: Сповіщення для відправки
            
        Returns:
            True якщо успішно відправлено
        """
        try:
            metadata = notification.get_metadata()
            bot_token = metadata.get('bot_token')
            chat_id = metadata.get('chat_id')
            
            if not bot_token or not chat_id:
                logger.error(f"Missing bot_token or chat_id for notification {notification.id}")
                return False
            
            telegram_service = TelegramService(bot_token)
            result = telegram_service.send_message_to_chat(
                chat_id=chat_id,
                message=notification.message_content
            )
            
            if result.get('success'):
                # Зберігаємо додаткову інформацію про відправлене повідомлення
                metadata.update({
                    'message_id': result.get('message_id'),
                    'sent_at': datetime.utcnow().isoformat()
                })
                notification.set_metadata(metadata)
                return True
            else:
                error_msg = result.get('error', 'Невідома помилка')
                notification.error_message = error_msg
                logger.error(f"Telegram send failed: {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"Error in _send_telegram_notification: {e}")
            return False
    
    def _send_email_notification(self, notification: NotificationQueue) -> bool:
        """
        Відправити email сповіщення
        
        Args:
            notification: Сповіщення для відправки
            
        Returns:
            True якщо успішно відправлено
        """
        try:
            if not self.smtp_username or not self.smtp_password:
                logger.error("SMTP credentials not configured")
                return False
            
            metadata = notification.get_metadata()
            email_address = metadata.get('email_address')
            restaurant_name = metadata.get('restaurant_name', 'Ресторан')
            
            if not email_address:
                logger.error(f"Missing email_address for notification {notification.id}")
                return False
            
            # Створюємо email повідомлення
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"Новий відгук - {restaurant_name}"
            msg['From'] = self.from_email
            msg['To'] = email_address
            
            # HTML версія повідомлення
            html_content = self._format_email_content(notification.message_content, restaurant_name)
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
            
            # Відправляємо email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {email_address}")
            return True
            
        except Exception as e:
            logger.error(f"Error in _send_email_notification: {e}")
            return False
    
    def _format_email_content(self, message_content: str, restaurant_name: str) -> str:
        """
        Форматувати зміст email повідомлення
        
        Args:
            message_content: Оригінальний зміст повідомлення
            restaurant_name: Назва ресторану
            
        Returns:
            HTML форматований зміст
        """
        # Конвертуємо Telegram HTML в email HTML
        html_content = message_content.replace('<b>', '<strong>').replace('</b>', '</strong>')
        html_content = html_content.replace('<i>', '<em>').replace('</i>', '</em>')
        html_content = html_content.replace('\n', '<br>')
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Новий відгук - {restaurant_name}</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2c3e50;">Новий відгук</h2>
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px;">
                    {html_content}
                </div>
                <hr style="margin: 20px 0;">
                <p style="font-size: 12px; color: #666;">
                    Це автоматичне повідомлення від системи збору відгуків {restaurant_name}.
                </p>
            </div>
        </body>
        </html>
        """
    
    def start_queue_processor(self):
        """Запустити обробник черги в окремому потоці"""
        if self._running:
            logger.warning("Queue processor is already running")
            return
        
        self._running = True
        self._worker_thread = threading.Thread(target=self._queue_worker, daemon=True)
        self._worker_thread.start()
        logger.info("Notification queue processor started")
    
    def stop_queue_processor(self):
        """Зупинити обробник черги"""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=10)
        logger.info("Notification queue processor stopped")
    
    def _queue_worker(self):
        """Робочий потік для обробки черги"""
        logger.info("Queue worker thread started")
        
        while self._running:
            try:
                with self.app.app_context():
                    stats = self.process_pending_notifications()
                    
                    if stats['processed'] > 0:
                        logger.info(f"Queue processing stats: {stats}")
                
                # Чекаємо перед наступною ітерацією
                time.sleep(self.queue_check_interval)
                
            except Exception as e:
                logger.error(f"Error in queue worker: {e}")
                time.sleep(self.queue_check_interval)
        
        logger.info("Queue worker thread stopped")
    
    def get_queue_stats(self) -> Dict[str, int]:
        """
        Отримати статистику черги сповіщень
        
        Returns:
            Словник зі статистикою
        """
        try:
            stats = {}
            
            # Загальна кількість по статусах
            for status in NotificationStatus:
                count = NotificationQueue.query.filter_by(status=status.value).count()
                stats[status.value] = count
            
            # Кількість готових для обробки
            ready_count = NotificationQueue.query.filter(
                and_(
                    NotificationQueue.status.in_([
                        NotificationStatus.PENDING.value,
                        NotificationStatus.RETRYING.value
                    ]),
                    NotificationQueue.scheduled_at <= datetime.utcnow()
                )
            ).count()
            stats['ready_for_processing'] = ready_count
            
            # Кількість за останню годину
            hour_ago = datetime.utcnow() - timedelta(hours=1)
            recent_count = NotificationQueue.query.filter(
                NotificationQueue.created_at >= hour_ago
            ).count()
            stats['created_last_hour'] = recent_count
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            return {}
    
    def cleanup_old_notifications(self, days_old: int = 30) -> int:
        """
        Очистити старі сповіщення
        
        Args:
            days_old: Кількість днів для збереження
            
        Returns:
            Кількість видалених записів
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            # Видаляємо тільки успішно відправлені або остаточно невдалі
            deleted = NotificationQueue.query.filter(
                and_(
                    NotificationQueue.created_at < cutoff_date,
                    NotificationQueue.status.in_([
                        NotificationStatus.SENT.value,
                        NotificationStatus.FAILED.value
                    ])
                )
            ).delete()
            
            db.session.commit()
            logger.info(f"Cleaned up {deleted} old notifications")
            return deleted
            
        except Exception as e:
            logger.error(f"Error cleaning up old notifications: {e}")
            db.session.rollback()
            return 0

    def _trigger_critical_alert(self, alert_type: str, error_message: str):
        """
        Тригер критичного алерту
        
        Args:
            alert_type: Тип алерту
            error_message: Повідомлення про помилку
        """
        try:
            alert_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'alert_type': alert_type,
                'error_message': error_message,
                'service': 'NotificationService',
                'severity': 'CRITICAL'
            }
            
            logger.critical("CRITICAL ALERT TRIGGERED", extra=alert_data)
            
            # Відправка алерту адміністраторам
            self._send_alert_to_admins(alert_data)
            
        except Exception as e:
            logger.error(f"Failed to trigger critical alert: {e}")
    
    def _send_alert_to_admins(self, alert_data: Dict[str, Any]):
        """
        Відправка критичного алерту адміністраторам
        
        Args:
            alert_data: Дані алерту
        """
        try:
            # Import here to avoid circular imports
            from models import AdminSettings
            
            # Формуємо повідомлення алерту
            alert_message = f"""
🚨 КРИТИЧНИЙ АЛЕРТ СИСТЕМИ СПОВІЩЕНЬ 🚨

⏰ Час: {alert_data['timestamp']}
🔧 Сервіс: {alert_data['service']}
⚠️ Тип алерту: {alert_data['alert_type']}
📝 Повідомлення: {alert_data['error_message']}
🔴 Рівень: {alert_data['severity']}

Будь ласка, перевірте систему сповіщень!
            """.strip()
            
            # Отримуємо налаштування алертів з бази даних
            alert_settings = AdminSettings.get_alert_settings()
            
            # Відправка email алерту
            if (alert_settings.get('alert_email_enabled') and 
                alert_settings.get('alert_email')):
                try:
                    self._send_alert_email(alert_settings['alert_email'], alert_message, alert_data)
                except Exception as e:
                    logger.error(f"Failed to send alert email: {e}")
            
            # Відправка Telegram алерту
            if (alert_settings.get('alert_telegram_enabled') and 
                alert_settings.get('alert_telegram_bot_token') and 
                alert_settings.get('alert_telegram_chat_id')):
                try:
                    self._send_alert_telegram(
                        alert_settings['alert_telegram_bot_token'],
                        alert_settings['alert_telegram_chat_id'],
                        alert_message
                    )
                except Exception as e:
                    logger.error(f"Failed to send alert telegram: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to send alert to admins: {e}")
    
    def _send_alert_email(self, alert_email: str, alert_message: str, alert_data: Dict[str, Any]):
        """
        Відправка алерту через email
        
        Args:
            alert_email: Email адреса для алертів
            alert_message: Текст повідомлення
            alert_data: Дані алерту
        """
        try:
            msg = MIMEMultipart()
            msg['From'] = self.app.config.get('MAIL_DEFAULT_SENDER', self.app.config.get('MAIL_USERNAME'))
            msg['To'] = alert_email
            msg['Subject'] = f"🚨 КРИТИЧНИЙ АЛЕРТ: {alert_data['alert_type']}"
            
            # HTML версія повідомлення
            html_message = f"""
            <html>
            <body>
                <h2 style="color: #dc3545;">🚨 КРИТИЧНИЙ АЛЕРТ СИСТЕМИ СПОВІЩЕНЬ</h2>
                <table style="border-collapse: collapse; width: 100%;">
                    <tr>
                        <td style="border: 1px solid #ddd; padding: 8px; font-weight: bold;">Час:</td>
                        <td style="border: 1px solid #ddd; padding: 8px;">{alert_data['timestamp']}</td>
                    </tr>
                    <tr>
                        <td style="border: 1px solid #ddd; padding: 8px; font-weight: bold;">Сервіс:</td>
                        <td style="border: 1px solid #ddd; padding: 8px;">{alert_data['service']}</td>
                    </tr>
                    <tr>
                        <td style="border: 1px solid #ddd; padding: 8px; font-weight: bold;">Тип алерту:</td>
                        <td style="border: 1px solid #ddd; padding: 8px;">{alert_data['alert_type']}</td>
                    </tr>
                    <tr>
                        <td style="border: 1px solid #ddd; padding: 8px; font-weight: bold;">Повідомлення:</td>
                        <td style="border: 1px solid #ddd; padding: 8px;">{alert_data['error_message']}</td>
                    </tr>
                    <tr>
                        <td style="border: 1px solid #ddd; padding: 8px; font-weight: bold;">Рівень:</td>
                        <td style="border: 1px solid #ddd; padding: 8px; color: #dc3545; font-weight: bold;">{alert_data['severity']}</td>
                    </tr>
                </table>
                <p style="margin-top: 20px; color: #856404; background-color: #fff3cd; padding: 10px; border: 1px solid #ffeaa7;">
                    <strong>Дія:</strong> Будь ласка, негайно перевірте систему сповіщень!
                </p>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(alert_message, 'plain', 'utf-8'))
            msg.attach(MIMEText(html_message, 'html', 'utf-8'))
            
            # Відправка email
            server = smtplib.SMTP(self.app.config['MAIL_SERVER'], self.app.config['MAIL_PORT'])
            if self.app.config.get('MAIL_USE_TLS'):
                server.starttls()
            
            if self.app.config.get('MAIL_USERNAME') and self.app.config.get('MAIL_PASSWORD'):
                server.login(self.app.config['MAIL_USERNAME'], self.app.config['MAIL_PASSWORD'])
            
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Critical alert email sent to {alert_email}")
            
        except Exception as e:
            logger.error(f"Failed to send alert email: {e}")
            raise
    
    def _send_alert_telegram(self, bot_token: str, chat_id: str, alert_message: str):
        """
        Відправка алерту через Telegram
        
        Args:
            bot_token: Токен Telegram бота
            chat_id: ID чату для алертів
            alert_message: Текст повідомлення
        """
        try:
            import requests
            
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': alert_message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            
            logger.info(f"Critical alert telegram sent to chat {chat_id}")
            
        except Exception as e:
            logger.error(f"Failed to send alert telegram: {e}")
            raise
    
    def get_metrics_report(self) -> Dict[str, Any]:
        """
        Отримати детальний звіт метрик
        
        Returns:
            Словник з метриками
        """
        try:
            from models import NotificationQueue, db
            
            queue_stats = self.get_queue_stats()
            
            # Отримуємо метрики з бази даних
            total_sent = db.session.query(NotificationQueue).filter_by(status='sent').count()
            total_failed = db.session.query(NotificationQueue).filter_by(status='failed').count()
            
            # Метрики по типах
            telegram_sent = db.session.query(NotificationQueue).filter_by(
                status='sent', notification_type='telegram'
            ).count()
            telegram_failed = db.session.query(NotificationQueue).filter_by(
                status='failed', notification_type='telegram'
            ).count()
            
            email_sent = db.session.query(NotificationQueue).filter_by(
                status='sent', notification_type='email'
            ).count()
            email_failed = db.session.query(NotificationQueue).filter_by(
                status='failed', notification_type='email'
            ).count()
            
            # Розрахунок відсотка успішності
            total_processed = total_sent + total_failed
            success_rate = (total_sent / total_processed * 100) if total_processed > 0 else 0
            
            # Середній час обробки (використовуємо дані з пам'яті, якщо є)
            average_processing_time = self.metrics.get_average_processing_time()
            
            report = {
                'timestamp': datetime.utcnow().isoformat(),
                'queue_stats': queue_stats,
                'performance_metrics': {
                    'total_sent': total_sent,
                    'total_failed': total_failed,
                    'success_rate': success_rate,
                    'average_processing_time': average_processing_time,
                    'telegram_stats': {
                        'sent': telegram_sent,
                        'failed': telegram_failed
                    },
                    'email_stats': {
                        'sent': email_sent,
                        'failed': email_failed
                    }
                },
                'error_breakdown': self.metrics.error_counts,
                'system_health': self._get_system_health()
            }
            
            logger.info("Metrics report generated", extra={
                'success_rate': report['performance_metrics']['success_rate'],
                'total_processed': total_processed,
                'queue_size': queue_stats.get('pending', 0) + queue_stats.get('retrying', 0)
            })
            
            return report
            
        except Exception as e:
            logger.error("Failed to generate metrics report", extra={'error': str(e)}, exc_info=True)
            return {}
    
    def _get_system_health(self) -> Dict[str, Any]:
        """
        Перевірити здоров'я системи
        
        Returns:
            Словник з показниками здоров'я
        """
        health = {
            'status': 'healthy',
            'issues': []
        }
        
        try:
            # Перевірка конфігурації SMTP
            if not self.smtp_username or not self.smtp_password:
                health['issues'].append('SMTP credentials not configured')
                health['status'] = 'degraded'
            
            # Перевірка черги
            queue_stats = self.get_queue_stats()
            failed_count = queue_stats.get('failed', 0)
            pending_count = queue_stats.get('pending', 0) + queue_stats.get('retrying', 0)
            
            if failed_count > 100:
                health['issues'].append(f'High number of failed notifications: {failed_count}')
                health['status'] = 'degraded'
            
            if pending_count > 500:
                health['issues'].append(f'Large queue backlog: {pending_count}')
                health['status'] = 'degraded'
            
            # Перевірка успішності
            success_rate = self.metrics.get_success_rate()
            if success_rate < 90 and (self.metrics.total_sent + self.metrics.total_failed) > 10:
                health['issues'].append(f'Low success rate: {success_rate:.1f}%')
                health['status'] = 'unhealthy'
            
            # Перевірка робочого потоку
            if not self._running:
                health['issues'].append('Queue processor is not running')
                health['status'] = 'unhealthy'
            
        except Exception as e:
            health['status'] = 'unknown'
            health['issues'].append(f'Health check failed: {str(e)}')
            logger.error("System health check failed", extra={'error': str(e)}, exc_info=True)
        
        return health
    
    def reset_metrics(self):
        """Скинути метрики (корисно для періодичних звітів)"""
        self.metrics.reset_metrics()
        logger.info("Notification metrics reset")