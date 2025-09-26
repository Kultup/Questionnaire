#!/usr/bin/env python3
"""
Міграція для додавання відсутніх колонок до таблиці notification_queue
"""

import sqlite3
import os

def run_migration():
    """Запуск міграції для додавання відсутніх колонок"""
    
    # Шлях до бази даних
    db_path = os.path.join('instance', 'feedback_system.db')
    
    if not os.path.exists(db_path):
        print(f"❌ База даних не знайдена: {db_path}")
        return False
    
    print("Запуск міграції для виправлення таблиці notification_queue...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Перевіряємо, чи існують колонки
        cursor.execute("PRAGMA table_info(notification_queue)")
        columns = [column[1] for column in cursor.fetchall()]
        
        print(f"Існуючі колонки: {columns}")
        
        # Додаємо відсутні колонки
        if 'survey_id' not in columns:
            print("Додавання колонки survey_id...")
            cursor.execute('''
                ALTER TABLE notification_queue 
                ADD COLUMN survey_id INTEGER REFERENCES surveys(id)
            ''')
            print("✅ Колонка survey_id додана")
        
        if 'metadata_json' not in columns:
            print("Додавання колонки metadata_json...")
            cursor.execute('''
                ALTER TABLE notification_queue 
                ADD COLUMN metadata_json TEXT
            ''')
            print("✅ Колонка metadata_json додана")
        
        # Перейменовуємо колонку message на message_content, якщо потрібно
        if 'message' in columns and 'message_content' not in columns:
            print("Створення нової таблиці з правильними назвами колонок...")
            
            # Створюємо тимчасову таблицю з правильною структурою
            cursor.execute('''
                CREATE TABLE notification_queue_new (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    survey_id INTEGER REFERENCES surveys(id),
                    notification_type VARCHAR(20) NOT NULL,
                    message_content TEXT NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 3,
                    scheduled_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    sent_at TIMESTAMP,
                    error_message TEXT,
                    metadata_json TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Копіюємо дані з старої таблиці
            cursor.execute('''
                INSERT INTO notification_queue_new 
                (id, user_id, notification_type, message_content, status, retry_count, 
                 max_retries, scheduled_at, sent_at, error_message, created_at, updated_at)
                SELECT id, user_id, notification_type, message, status, retry_count,
                       max_retries, scheduled_at, sent_at, error_message, created_at, updated_at
                FROM notification_queue
            ''')
            
            # Видаляємо стару таблицю
            cursor.execute('DROP TABLE notification_queue')
            
            # Перейменовуємо нову таблицю
            cursor.execute('ALTER TABLE notification_queue_new RENAME TO notification_queue')
            
            print("✅ Таблиця оновлена з правильними назвами колонок")
        
        # Створюємо індекси для продуктивності
        print("Створення індексів...")
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_notification_queue_status ON notification_queue(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_notification_queue_scheduled ON notification_queue(scheduled_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_notification_queue_user ON notification_queue(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_notification_queue_survey ON notification_queue(survey_id)')
            print("✅ Індекси створено")
        except sqlite3.Error as e:
            print(f"⚠️ Помилка при створенні індексів: {e}")
        
        conn.commit()
        print("✅ Міграція завершена успішно!")
        
        # Перевіряємо результат
        cursor.execute("PRAGMA table_info(notification_queue)")
        new_columns = cursor.fetchall()
        print("Нова структура таблиці:")
        for column in new_columns:
            print(f"  {column[1]} ({column[2]}) - NOT NULL: {column[3]}, DEFAULT: {column[4]}, PK: {column[5]}")
        
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Помилка міграції: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    success = run_migration()
    if success:
        print("🎉 Міграція завершена успішно!")
    else:
        print("💥 Міграція не вдалася!")
        exit(1)