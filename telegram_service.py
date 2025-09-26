"""
Telegram Service Module
Модуль для роботи з Telegram Bot API та відправки повідомлень в групи
"""

import requests
import logging
from typing import Optional, Dict, Any
import asyncio
import time
import random
from datetime import datetime, timedelta
from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

class CircuitBreakerError(Exception):
    """Виняток для circuit breaker"""
    pass

class CircuitBreaker:
    """Circuit Breaker для запобігання каскадним збоям"""
    
    def __init__(self, failure_threshold=5, recovery_timeout=60, expected_exception=Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func, *args, **kwargs):
        """Виконати функцію з circuit breaker"""
        if self.state == 'OPEN':
            if self._should_attempt_reset():
                self.state = 'HALF_OPEN'
            else:
                raise CircuitBreakerError("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self):
        """Перевірити, чи слід спробувати скинути circuit breaker"""
        return (self.last_failure_time and 
                datetime.now() - self.last_failure_time >= timedelta(seconds=self.recovery_timeout))
    
    def _on_success(self):
        """Обробити успішний виклик"""
        self.failure_count = 0
        self.state = 'CLOSED'
    
    def _on_failure(self):
        """Обробити невдалий виклик"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'

class TelegramService:
    """Сервіс для роботи з Telegram Bot API"""
    
    def __init__(self, bot_token: str, max_retries: int = 3, retry_delay: float = 1.0):
        """
        Ініціалізація сервісу
        
        Args:
            bot_token: Токен Telegram бота
            max_retries: Максимальна кількість повторних спроб
            retry_delay: Базова затримка між спробами (секунди)
        """
        self.bot_token = bot_token
        self.bot = Bot(token=bot_token)
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Circuit breaker для запобігання каскадним збоям
        self.circuit_breaker = CircuitBreaker(
             failure_threshold=5,
             recovery_timeout=300,  # 5 хвилин
             expected_exception=(requests.exceptions.RequestException, TelegramError)
         )
    
    def _exponential_backoff(self, attempt: int) -> float:
        """
        Розрахунок затримки з експоненційним backoff та jitter
        
        Args:
            attempt: Номер спроби (починаючи з 0)
            
        Returns:
            Затримка в секундах
        """
        # Експоненційний backoff: base_delay * (2 ^ attempt)
        delay = self.retry_delay * (2 ** attempt)
        
        # Додаємо jitter для уникнення thundering herd
        jitter = random.uniform(0.1, 0.5)
        
        return min(delay + jitter, 60)  # Максимум 60 секунд
    
    def _retry_with_backoff(self, func, *args, **kwargs) -> Dict[str, Any]:
        """
        Виконати функцію з retry логікою та exponential backoff
        
        Args:
            func: Функція для виконання
            *args, **kwargs: Аргументи функції
            
        Returns:
            Результат виконання функції
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # Використовуємо circuit breaker
                return self.circuit_breaker.call(func, *args, **kwargs)
                
            except CircuitBreakerError as e:
                logger.warning(f"Circuit breaker is open: {e}")
                return {
                    'success': False,
                    'error': 'Сервіс тимчасово недоступний. Спробуйте пізніше.',
                    'retry_after': self.circuit_breaker.recovery_timeout
                }
                
            except (requests.exceptions.RequestException, TelegramError) as e:
                last_exception = e
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                
                if attempt < self.max_retries:
                    delay = self._exponential_backoff(attempt)
                    logger.info(f"Retrying in {delay:.2f} seconds...")
                    time.sleep(delay)
                else:
                    logger.error(f"All {self.max_retries + 1} attempts failed")
                    break
        
        # Всі спроби невдалі
        return {
            'success': False,
            'error': f'Не вдалося виконати запит після {self.max_retries + 1} спроб: {str(last_exception)}',
            'last_exception': str(last_exception)
        }
    
    def validate_bot_token(self) -> Dict[str, Any]:
        """
        Перевірка валідності токена бота
        
        Returns:
            Dict з інформацією про результат перевірки
        """
        try:
            response = requests.get(f"{self.base_url}/getMe", timeout=10)
            
            if response.status_code == 200:
                bot_info = response.json()
                if bot_info.get('ok'):
                    return {
                        'valid': True,
                        'bot_info': bot_info.get('result', {}),
                        'error': None
                    }
                else:
                    return {
                        'valid': False,
                        'bot_info': None,
                        'error': bot_info.get('description', 'Невідома помилка')
                    }
            else:
                return {
                    'valid': False,
                    'bot_info': None,
                    'error': f'HTTP {response.status_code}: {response.text}'
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error validating bot token: {e}")
            return {
                'valid': False,
                'bot_info': None,
                'error': f'Помилка з\'єднання: {str(e)}'
            }
    
    def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        """
        Отримання інформації про чат/групу
        
        Args:
            chat_id: ID чату або групи
            
        Returns:
            Dict з інформацією про чат
        """
        try:
            response = requests.get(
                f"{self.base_url}/getChat",
                params={'chat_id': chat_id},
                timeout=10
            )
            
            if response.status_code == 200:
                chat_info = response.json()
                if chat_info.get('ok'):
                    return {
                        'success': True,
                        'chat_info': chat_info.get('result', {}),
                        'error': None
                    }
                else:
                    return {
                        'success': False,
                        'chat_info': None,
                        'error': chat_info.get('description', 'Невідома помилка')
                    }
            else:
                return {
                    'success': False,
                    'chat_info': None,
                    'error': f'HTTP {response.status_code}: {response.text}'
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting chat info: {e}")
            return {
                'success': False,
                'chat_info': None,
                'error': f'Помилка з\'єднання: {str(e)}'
            }
    
    def get_available_groups(self) -> Dict[str, Any]:
        """
        Отримання списку доступних груп з оновлень бота
        
        Returns:
            Dict з інформацією про доступні групи
        """
        try:
            # Спочатку отримуємо всі оновлення
            response = requests.get(
                f"{self.base_url}/getUpdates",
                params={'limit': 100},
                timeout=10
            )
            
            if response.status_code != 200:
                return {
                    'success': False,
                    'groups': [],
                    'error': f'HTTP {response.status_code}: {response.text}',
                    'instructions': 'Перевірте токен бота та з\'єднання з інтернетом.'
                }
            
            updates_data = response.json()
            if not updates_data.get('ok'):
                return {
                    'success': False,
                    'groups': [],
                    'error': updates_data.get('description', 'Невідома помилка'),
                    'instructions': 'Перевірте правильність токена бота.'
                }
            
            updates = updates_data.get('result', [])
            groups = {}
            
            # Обробляємо оновлення для пошуку груп
            for update in updates:
                chat = None
                
                # Перевіряємо різні типи оновлень
                if 'message' in update:
                    chat = update['message'].get('chat')
                elif 'edited_message' in update:
                    chat = update['edited_message'].get('chat')
                elif 'channel_post' in update:
                    chat = update['channel_post'].get('chat')
                elif 'edited_channel_post' in update:
                    chat = update['edited_channel_post'].get('chat')
                elif 'my_chat_member' in update:
                    # Обробляємо зміни статусу бота в чаті
                    chat = update['my_chat_member'].get('chat')
                
                if chat and chat.get('type') in ['group', 'supergroup']:
                    chat_id = str(chat.get('id'))
                    chat_title = chat.get('title', 'Без назви')
                    chat_type = chat.get('type')
                    
                    # Зберігаємо унікальні групи
                    if chat_id not in groups:
                        groups[chat_id] = {
                            'id': chat_id,
                            'title': chat_title,
                            'type': chat_type,
                            'username': chat.get('username', None)
                        }
            
            if not groups:
                return {
                    'success': True,
                    'groups': [],
                    'error': None,
                    'instructions': 'Групи не знайдено в останніх оновленнях. Спробуйте:\n1. Надішліть будь-яке повідомлення в групу де є бот\n2. Додайте бота до групи як адміністратора\n3. Використайте команду /start в групі\n4. Спробуйте знову через кілька хвилин'
                }
            
            return {
                'success': True,
                'groups': list(groups.values()),
                'error': None,
                'instructions': None
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting available groups: {e}")
            return {
                'success': False,
                'groups': [],
                'error': f'Помилка з\'єднання: {str(e)}',
                'instructions': 'Перевірте з\'єднання з інтернетом та спробуйте знову.'
            }
    
    def send_group_discovery_message(self, chat_id: str) -> Dict[str, Any]:
        """
        Відправляє повідомлення для виявлення ID групи
        
        Args:
            chat_id: ID чату для відправки повідомлення
            
        Returns:
            Dict з інформацією про чат та його ID
        """
        try:
            message = "🤖 Тест з'єднання з ботом\n\nЦе повідомлення підтверджує, що бот працює в цій групі."
            
            response = requests.post(
                f"{self.base_url}/sendMessage",
                json={
                    'chat_id': chat_id,
                    'text': message,
                    'parse_mode': 'HTML'
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    message_data = result.get('result', {})
                    chat_data = message_data.get('chat', {})
                    
                    return {
                        'success': True,
                        'chat_info': {
                            'id': str(chat_data.get('id')),
                            'title': chat_data.get('title', 'Без назви'),
                            'type': chat_data.get('type'),
                            'username': chat_data.get('username')
                        },
                        'error': None
                    }
                else:
                    return {
                        'success': False,
                        'chat_info': None,
                        'error': result.get('description', 'Невідома помилка')
                    }
            else:
                return {
                    'success': False,
                    'chat_info': None,
                    'error': f'HTTP {response.status_code}: {response.text}'
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending group discovery message: {e}")
            return {
                'success': False,
                'chat_info': None,
                'error': f'Помилка з\'єднання: {str(e)}'
            }
    
    def _send_message_internal(self, chat_id: str, message: str, parse_mode: str = 'HTML') -> Dict[str, Any]:
        """
        Внутрішній метод для відправки повідомлення (без retry логіки)
        
        Args:
            chat_id: ID чату або групи
            message: Текст повідомлення
            parse_mode: Режим парсингу (HTML або Markdown)
            
        Returns:
            Dict з результатом відправки
        """
        data = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': parse_mode
        }
        
        response = requests.post(
            f"{self.base_url}/sendMessage",
            json=data,
            timeout=30  # Збільшено timeout
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                return {
                    'success': True,
                    'message_info': result.get('result', {}),
                    'error': None,
                    'message_id': result.get('result', {}).get('message_id'),
                    'chat_info': result.get('result', {}).get('chat', {})
                }
            else:
                error_code = result.get('error_code')
                description = result.get('description', 'Невідома помилка')
                
                # Обробка специфічних помилок Telegram
                if error_code == 400:
                    if 'chat not found' in description.lower():
                        raise requests.exceptions.RequestException(f"Чат не знайдено: {chat_id}")
                    elif 'bot was blocked' in description.lower():
                        raise requests.exceptions.RequestException(f"Бот заблокований користувачем")
                elif error_code == 403:
                    if 'bot is not a member' in description.lower():
                        raise requests.exceptions.RequestException(f"Бот не є учасником групи")
                    elif 'not enough rights' in description.lower():
                        raise requests.exceptions.RequestException(f"Недостатньо прав для відправки повідомлень")
                elif error_code == 429:
                    # Rate limiting
                    retry_after = result.get('parameters', {}).get('retry_after', 60)
                    raise requests.exceptions.RequestException(f"Перевищено ліміт запитів. Повторіть через {retry_after} секунд")
                
                raise requests.exceptions.RequestException(f"Telegram API Error {error_code}: {description}")
        else:
            raise requests.exceptions.RequestException(f'HTTP {response.status_code}: {response.text}')

    def send_message_to_chat(self, chat_id: str, message: str, parse_mode: str = 'HTML') -> Dict[str, Any]:
        """
        Відправка повідомлення в чат або групу з retry логікою
        
        Args:
            chat_id: ID чату або групи
            message: Текст повідомлення
            parse_mode: Режим парсингу (HTML або Markdown)
            
        Returns:
            Dict з результатом відправки
        """
        logger.info(f"Sending message to chat {chat_id}")
        
        # Валідація вхідних даних
        if not chat_id:
            return {
                'success': False,
                'message_info': None,
                'error': 'ID чату не може бути порожнім'
            }
        
        if not message or len(message.strip()) == 0:
            return {
                'success': False,
                'message_info': None,
                'error': 'Повідомлення не може бути порожнім'
            }
        
        # Перевірка довжини повідомлення (Telegram ліміт 4096 символів)
        if len(message) > 4096:
            logger.warning(f"Message too long ({len(message)} chars), truncating...")
            message = message[:4093] + "..."
        
        return self._retry_with_backoff(
            self._send_message_internal,
            chat_id=chat_id,
            message=message,
            parse_mode=parse_mode
        )
    
    def send_test_message(self, chat_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Відправка тестового повідомлення
        
        Args:
            chat_id: ID чату для тестування (якщо None, відправляється боту)
            
        Returns:
            Dict з результатом відправки
        """
        test_message = """
🤖 <b>Тестове повідомлення</b>

✅ Ваш Telegram бот успішно налаштований!
📱 Сповіщення про нові відгуки будуть надходити в цю групу.

<i>Це тестове повідомлення можна видалити.</i>
        """.strip()
        
        if chat_id:
            return self.send_message_to_chat(chat_id, test_message)
        else:
            # Відправка тестового повідомлення боту (getMe)
            try:
                response = requests.get(f"{self.base_url}/getMe", timeout=10)
                if response.status_code == 200:
                    return {
                        'success': True,
                        'message_info': {'test': 'Bot token is valid'},
                        'error': None
                    }
                else:
                    return {
                        'success': False,
                        'message_info': None,
                        'error': 'Невалідний токен бота'
                    }
            except Exception as e:
                return {
                    'success': False,
                    'message_info': None,
                    'error': str(e)
                }
    
    def check_bot_permissions(self, chat_id: str) -> Dict[str, Any]:
        """
        Перевірка прав бота в групі
        
        Args:
            chat_id: ID групи
            
        Returns:
            Dict з інформацією про права бота
        """
        try:
            # Отримуємо інформацію про бота
            bot_info = self.validate_bot_token()
            if not bot_info['valid']:
                return {
                    'success': False,
                    'permissions': None,
                    'error': 'Невалідний токен бота'
                }
            
            bot_id = bot_info['bot_info']['id']
            
            # Перевіряємо статус бота в чаті
            response = requests.get(
                f"{self.base_url}/getChatMember",
                params={'chat_id': chat_id, 'user_id': bot_id},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    member_info = result.get('result', {})
                    status = member_info.get('status')
                    
                    if status in ['administrator', 'creator']:
                        return {
                            'success': True,
                            'permissions': {
                                'status': status,
                                'can_send_messages': True,
                                'member_info': member_info
                            },
                            'error': None
                        }
                    elif status == 'member':
                        return {
                            'success': True,
                            'permissions': {
                                'status': status,
                                'can_send_messages': True,
                                'member_info': member_info
                            },
                            'error': None
                        }
                    else:
                        return {
                            'success': False,
                            'permissions': None,
                            'error': f'Бот має статус "{status}" і не може відправляти повідомлення'
                        }
                else:
                    return {
                        'success': False,
                        'permissions': None,
                        'error': result.get('description', 'Не вдалося отримати інформацію про права бота')
                    }
            else:
                return {
                    'success': False,
                    'permissions': None,
                    'error': f'HTTP {response.status_code}: {response.text}'
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error checking bot permissions: {e}")
            return {
                'success': False,
                'permissions': None,
                'error': f'Помилка з\'єднання: {str(e)}'
            }


def create_feedback_message(restaurant_name: str, waiter_name: str, overall_score: int, 
                          answers: list, survey_id: int = None) -> str:
    """
    Створення форматованого повідомлення про новий відгук
    
    Args:
        restaurant_name: Назва ресторану
        waiter_name: Ім'я офіціанта
        overall_score: Загальна оцінка
        answers: Список відповідей на питання
        survey_id: ID опитування (опціонально)
        
    Returns:
        Форматований текст повідомлення
    """
    message = f"🍽️ <b>Новий відгук для {restaurant_name}</b>\n\n"
    message += f"👨‍💼 <b>Офіціант:</b> {waiter_name}\n"
    message += f"⭐ <b>Загальна оцінка:</b> {overall_score}/10\n"
    
    if survey_id:
        message += f"🆔 <b>ID відгуку:</b> #{survey_id}\n"
    
    message += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for answer in answers:
        question_text = answer.get('question', '')
        answer_value = answer.get('answer', '')
        comment = answer.get('comment', '')
        question_type = answer.get('type', 'yes_no')
        
        if question_type == 'yes_no':
            message += f"❓ <b>{question_text}</b>\n"
            answer_emoji = "✅" if answer_value == 'Так' else "❌"
            message += f"{answer_emoji} <b>Відповідь:</b> {answer_value}\n"
            if comment:
                message += f"💬 <b>Коментар:</b> <i>{comment}</i>\n"
        else:
            message += f"📝 <b>{question_text}</b>\n"
            message += f"💭 <b>Відповідь:</b> <i>{answer_value}</i>\n"
        
        message += "\n"
    
    return message