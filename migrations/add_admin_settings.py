"""
Міграція для додавання таблиці admin_settings
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, AdminSettings

def upgrade():
    """Створити таблицю admin_settings"""
    print("Створення таблиці admin_settings...")
    
    # Створюємо таблицю
    db.create_all()
    
    # Додаємо початкові налаштування алертів
    default_settings = [
        ('alert_email', '', 'string', 'Email адреса для критичних алертів', False),
        ('alert_telegram_bot_token', '', 'string', 'Токен Telegram бота для алертів', True),
        ('alert_telegram_chat_id', '', 'string', 'ID чату Telegram для алертів', False),
        ('alert_email_enabled', 'false', 'boolean', 'Увімкнути email алерти', False),
        ('alert_telegram_enabled', 'false', 'boolean', 'Увімкнути Telegram алерти', False),
    ]
    
    for key, value, setting_type, description, is_sensitive in default_settings:
        existing = AdminSettings.query.filter_by(setting_key=key).first()
        if not existing:
            setting = AdminSettings(
                setting_key=key,
                setting_value=value,
                setting_type=setting_type,
                description=description,
                is_sensitive=is_sensitive
            )
            db.session.add(setting)
    
    db.session.commit()
    print("Таблиця admin_settings створена успішно!")

def downgrade():
    """Видалити таблицю admin_settings"""
    print("Видалення таблиці admin_settings...")
    db.drop_all(tables=[AdminSettings.__table__])
    print("Таблиця admin_settings видалена!")

if __name__ == '__main__':
    from app import app
    with app.app_context():
        upgrade()