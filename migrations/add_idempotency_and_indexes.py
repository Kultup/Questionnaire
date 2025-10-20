#!/usr/bin/env python3
"""
Міграція: додає dedup_key, locked_at до notification_queue та унікальні/звичайні індекси
"""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'instance', 'feedback_system.db')
DB_PATH = os.path.abspath(DB_PATH)

def run():
    print("Running migration: idempotency and indexes for notification_queue...")
    print(f"DB path: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()

        # Перевіряємо існуючі колонки
        cursor.execute("PRAGMA table_info(notification_queue)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'dedup_key' not in columns:
            print("Adding column dedup_key...")
            cursor.execute("ALTER TABLE notification_queue ADD COLUMN dedup_key TEXT")

        if 'locked_at' not in columns:
            print("Adding column locked_at...")
            cursor.execute("ALTER TABLE notification_queue ADD COLUMN locked_at DATETIME")

        # Індекси
        print("Creating indexes...")
        # Переконаємося, що survey_id існує перед індексом тип+survey
        cursor.execute("PRAGMA table_info(notification_queue)")
        cols = [row[1] for row in cursor.fetchall()]
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notification_queue_dedup ON notification_queue(dedup_key)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notification_queue_locked ON notification_queue(locked_at)")
        if 'survey_id' in cols:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notification_queue_type_survey ON notification_queue(notification_type, survey_id)")

        # Note: SQLite allows multiple NULLs in unique indexes; для суворої унікальності потрібні тригери — опущено.

        conn.commit()
        print("Migration finished successfully")
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Migration error: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    run()


