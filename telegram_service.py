"""
Telegram Service Module
Модуль для роботи з Telegram Bot API та відправки повідомлень в групи
"""

import requests
import logging
from typing import Optional, Dict, Any
import asyncio
from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

class TelegramService:
    """Сервіс для роботи з Telegram Bot API"""
    
    def __init__(self, bot_token: str):
        """
        Ініціалізація сервісу
        
        Args:
            bot_token: Токен Telegram бота
        """
        self.bot_token = bot_token
        self.bot = Bot(token=bot_token)
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
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
    
    def send_message_to_chat(self, chat_id: str, message: str, parse_mode: str = 'HTML') -> Dict[str, Any]:
        """
        Відправка повідомлення в чат або групу
        
        Args:
            chat_id: ID чату або групи
            message: Текст повідомлення
            parse_mode: Режим парсингу (HTML або Markdown)
            
        Returns:
            Dict з результатом відправки
        """
        try:
            data = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': parse_mode
            }
            
            response = requests.post(
                f"{self.base_url}/sendMessage",
                json=data,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    return {
                        'success': True,
                        'message_info': result.get('result', {}),
                        'error': None
                    }
                else:
                    return {
                        'success': False,
                        'message_info': None,
                        'error': result.get('description', 'Невідома помилка')
                    }
            else:
                return {
                    'success': False,
                    'message_info': None,
                    'error': f'HTTP {response.status_code}: {response.text}'
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending message to chat {chat_id}: {e}")
            return {
                'success': False,
                'message_info': None,
                'error': f'Помилка з\'єднання: {str(e)}'
            }
    
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