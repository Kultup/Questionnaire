"""
Міграція для додавання полів telegram_group_name та telegram_group_link до таблиці users
"""

import sqlite3
import os

def migrate():
    """Виконати міграцію"""
    db_path = os.path.join('instance', 'feedback_system.db')
    
    if not os.path.exists(db_path):
        print(f"❌ База даних не знайдена: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Перевіряємо, чи існують поля
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        migrations_applied = 0
        
        # Додаємо telegram_group_name якщо не існує
        if 'telegram_group_name' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN telegram_group_name VARCHAR(200)')
            print("✅ Додано поле telegram_group_name")
            migrations_applied += 1
        else:
            print("ℹ️ Поле telegram_group_name вже існує")
        
        # Додаємо telegram_group_link якщо не існує
        if 'telegram_group_link' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN telegram_group_link VARCHAR(200)')
            print("✅ Додано поле telegram_group_link")
            migrations_applied += 1
        else:
            print("ℹ️ Поле telegram_group_link вже існує")
        
        conn.commit()
        conn.close()
        
        if migrations_applied > 0:
            print(f"🎉 Міграція завершена! Додано {migrations_applied} нових полів.")
        else:
            print("ℹ️ Всі поля вже існують, міграція не потрібна.")
        
        return True
        
    except Exception as e:
        print(f"❌ Помилка під час міграції: {e}")
        return False

if __name__ == '__main__':
    migrate()